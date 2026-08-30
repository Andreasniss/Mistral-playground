import json
import random
import time
import uuid
from collections.abc import Callable

from mistralai.client import Mistral
from openai import OpenAI

# OpenTelemetry instrumentation
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

import config
from logger import get_logger


def _configure_tracing() -> bool:
    """Configure OTLP tracing when explicitly enabled.

    Tracing is disabled by default so imports and tests do not open a network
    connection. Prompt and response content are intentionally never exported.
    """
    if not config.OTEL_ENABLED:
        return False

    resource = Resource.create({"service.name": "mistral-playground"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=config.OTEL_EXPORTER_OTLP_ENDPOINT,
                insecure=config.OTEL_EXPORTER_OTLP_ENDPOINT.startswith("http://"),
            )
        )
    )
    trace.set_tracer_provider(provider)
    return True


_configure_tracing()

logger = get_logger("llm_client")

# Singleton client — created once and reused across all calls.
# When LLM_BACKEND=api  → Mistral SDK pointing at the cloud API.
# When LLM_BACKEND=local → OpenAI SDK pointing at the local Ollama server
#                          (Ollama exposes an OpenAI-compatible endpoint).
_client = None

# Status codes worth retrying, per Mistral API docs:
# 429 — rate limit exceeded (slow down and try again)
# 500/502/503/504 — transient server-side errors
# Do NOT retry 4xx client errors (401 bad key, 422 bad payload) — those won't
# resolve by themselves and retrying wastes quota.
# https://docs.mistral.ai/api/
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def get_client():
    """Return the shared client, creating it on first call.

    Returns a Mistral client when LLM_BACKEND=api, or an OpenAI client
    (pointed at the local Ollama server) when LLM_BACKEND=local.
    """
    global _client
    if _client is None:
        config.validate_runtime_config()
        if config.LLM_BACKEND == "local":
            _client = OpenAI(
                base_url=config.OLLAMA_BASE_URL,
                api_key="ollama",
                timeout=config.REQUEST_TIMEOUT,
            )
            logger.info("Using local Ollama backend")
        else:
            _client = Mistral(api_key=config.MISTRAL_API_KEY)
            logger.info("Using Mistral cloud API backend")
    return _client


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception represents a transient, retryable error."""
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status in _RETRYABLE_STATUS_CODES
    # Fallback: some SDK versions embed the status code in the message string
    # rather than exposing it as an attribute.
    return any(str(code) in str(exc) for code in _RETRYABLE_STATUS_CODES)


def _get_retry_after(exc: Exception) -> float | None:
    """Extract the Retry-After value (seconds) from the exception headers.

    The Mistral API sets a Retry-After header on 429 responses to tell clients
    exactly how long to wait. Honouring it is more precise than guessing with
    exponential backoff alone.
    https://docs.mistral.ai/api/
    """
    # The SDK may expose headers directly on the exception or via .response
    headers = getattr(exc, "headers", None)
    if headers is None:
        response = getattr(exc, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None)
    if headers is None:
        return None
    # Header names are case-insensitive in HTTP; check both casings defensively
    value = headers.get("Retry-After") or headers.get("retry-after")
    if value is not None:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


def _call_with_retry(fn, trace_id: str):
    """Call fn(), retrying on transient errors with exponential backoff + jitter.

    Delay formula per Mistral docs recommendation:
        delay = min(base_delay * 2^attempt + jitter, max_delay)
    where jitter is a small random value (0–0.5 s) that prevents all clients
    from retrying at the exact same moment (thundering herd problem).

    If the server returns a Retry-After header, that value takes precedence
    over the calculated delay.
    """
    last_exc = None
    for attempt in range(config.RETRY_MAX_ATTEMPTS):
        try:
            return fn()
        except Exception as exc:
            if not _is_retryable(exc):
                raise  # 4xx client errors — no point retrying
            last_exc = exc
            if attempt == config.RETRY_MAX_ATTEMPTS - 1:
                break  # exhausted all attempts; will raise below

            # Prefer the server's Retry-After hint; fall back to backoff formula
            retry_after = _get_retry_after(exc)
            if retry_after is not None:
                delay = retry_after
            else:
                delay = min(
                    config.RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5),
                    config.RETRY_MAX_DELAY,
                )

            logger.warning(
                "[%s] Retryable error_type=%s status=%s, attempt %d/%d — retrying in %.1fs%s",
                trace_id,
                type(exc).__name__,
                getattr(exc, "status_code", "unknown"),
                attempt + 1,
                config.RETRY_MAX_ATTEMPTS,
                delay,
                " (Retry-After header)" if retry_after is not None else "",
            )
            time.sleep(delay)
    raise last_exc


def chat(
    user_message: str,
    system_message: str | None = None,
    conversation_history: list[dict] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """Send a chat message to Mistral and return the assistant reply as a string.

    Args:
        user_message:   The user turn to send.
        system_message: Optional system prompt to prepend (sets assistant behaviour).
        conversation_history: Prior user/assistant turns for multi-turn chat.
        model:          Override the model from config (e.g. "mistral-small-latest").
        max_tokens:     Override the token limit from config.
        temperature:    Override the sampling temperature from config (0.0–0.7).
        top_p:          Override nucleus sampling from config (0.0–1.0). Do not use
                        together with temperature.

    Returns:
        The assistant's reply as a plain string.

    Raises:
        Exception: Re-raises any API error after all retry attempts are exhausted.
    """
    # Short random ID attached to every log line for this call so request and
    # response entries can be correlated in the log file.
    trace_id = uuid.uuid4().hex[:8]
    resolved_model = model or config.MISTRAL_MODEL
    resolved_top_p = top_p if top_p is not None else config.MISTRAL_TOP_P

    # Build the messages array. System message must come first if present.
    # Valid roles: "system", "user", "assistant", "tool"
    # https://docs.mistral.ai/capabilities/completion/
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    logger.info(
        "[%s] Request — model=%s max_tokens=%s temperature=%s top_p=%s input_chars=%d",
        trace_id,
        resolved_model,
        max_tokens or config.MISTRAL_MAX_TOKENS,
        temperature if temperature is not None else config.MISTRAL_TEMPERATURE,
        resolved_top_p,
        len(user_message),
    )

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        "mistral_chat",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute("model", resolved_model)
        span.set_attribute("input_chars", len(user_message))
        span.set_attribute("max_tokens", max_tokens or config.MISTRAL_MAX_TOKENS)
        span.set_attribute(
            "temperature",
            temperature if temperature is not None else config.MISTRAL_TEMPERATURE,
        )
        if resolved_top_p is not None:
            span.set_attribute("top_p", resolved_top_p)

        start = time.perf_counter()
        try:
            if config.LLM_BACKEND == "local":
                response = _call_with_retry(
                    lambda: get_client().chat.completions.create(
                        model=resolved_model,
                        messages=messages,
                        max_tokens=max_tokens or config.MISTRAL_MAX_TOKENS,
                        temperature=(
                            temperature
                            if temperature is not None
                            else config.MISTRAL_TEMPERATURE
                        ),
                        **({"top_p": resolved_top_p} if resolved_top_p is not None else {}),
                    ),
                    trace_id,
                )
            else:
                response = _call_with_retry(
                    lambda: get_client().chat.complete(
                        model=resolved_model,
                        messages=messages,
                        max_tokens=max_tokens or config.MISTRAL_MAX_TOKENS,
                        temperature=(
                            temperature
                            if temperature is not None
                            else config.MISTRAL_TEMPERATURE
                        ),
                        **({"top_p": resolved_top_p} if resolved_top_p is not None else {}),
                    ),
                    trace_id,
                )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            span.set_attribute("error.type", type(exc).__name__)
            span.set_attribute("latency_seconds", elapsed)
            logger.error(
                "[%s] Request failed after %.2fs — error_type=%s",
                trace_id,
                elapsed,
                type(exc).__name__,
            )
            raise

        elapsed = time.perf_counter() - start
        usage = response.usage
        content = response.choices[0].message.content
        span.set_attribute("latency_seconds", elapsed)
        span.set_attribute("prompt_tokens", usage.prompt_tokens)
        span.set_attribute("completion_tokens", usage.completion_tokens)
        span.set_attribute("total_tokens", usage.total_tokens)
        span.set_attribute("output_chars", len(content or ""))

        logger.info(
            "[%s] Response — latency=%.2fs prompt_tokens=%s completion_tokens=%s total_tokens=%s output_chars=%d",
            trace_id,
            elapsed,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            len(content or ""),
        )

        return content


def chat_with_tools(
    user_message: str,
    tools: list[dict],
    tool_executor: Callable[[str, dict], str],
    system_message: str | None = None,
    conversation_history: list[dict] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
) -> str:
    """Send a chat message with tool definitions and handle the full tool-call loop.

    The model may respond by requesting one or more tool calls. This function
    executes each tool via `tool_executor`, appends the results, and calls the
    API again until the model produces a final text response.

    Args:
        user_message:   The user turn to send.
        tools:          List of tool definitions in OpenAI/Mistral format:
                        [{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]
        tool_executor:  Callable(name, args) → str. Called for each tool the model
                        requests. Return value is sent back as the tool result.
        system_message: Optional system prompt.
        conversation_history: Prior user/assistant turns for multi-turn chat.
        model:          Override the model from config.
        max_tokens:     Override the token limit from config.
        temperature:    Override the sampling temperature from config.
        top_p:          Override nucleus sampling from config.

    Returns:
        The assistant's final reply as a plain string.
    """
    resolved_model = model or config.MISTRAL_MODEL
    resolved_top_p = top_p if top_p is not None else config.MISTRAL_TOP_P
    resolved_temp = temperature if temperature is not None else config.MISTRAL_TEMPERATURE
    resolved_max_tokens = max_tokens or config.MISTRAL_MAX_TOKENS

    trace_id = uuid.uuid4().hex[:8]

    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    logger.info(
        "[%s] Tool-call request — model=%s tools=%s input_chars=%d",
        trace_id,
        resolved_model,
        [t["function"]["name"] for t in tools],
        len(user_message),
    )

    extra = {"top_p": resolved_top_p} if resolved_top_p is not None else {}

    def _call(msgs):
        if config.LLM_BACKEND == "local":
            return get_client().chat.completions.create(
                model=resolved_model,
                messages=msgs,
                tools=tools,
                max_tokens=resolved_max_tokens,
                temperature=resolved_temp,
                **extra,
            )
        return get_client().chat.complete(
            model=resolved_model,
            messages=msgs,
            tools=tools,
            max_tokens=resolved_max_tokens,
            temperature=resolved_temp,
            **extra,
        )

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span(
        "mistral_chat_with_tools",
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        span.set_attribute("input_chars", len(user_message))
        span.set_attribute("num_tools", len(tools))
        span.set_attribute("model", resolved_model)
        span.set_attribute("max_tokens", resolved_max_tokens)
        span.set_attribute("temperature", resolved_temp)
        if resolved_top_p is not None:
            span.set_attribute("top_p", resolved_top_p)

        start = time.perf_counter()
        try:
            response = _call_with_retry(lambda: _call(messages), trace_id)

            # Tool-call loop — bounded so a model cannot recurse indefinitely.
            tool_rounds = 0
            while response.choices[0].finish_reason == "tool_calls":
                tool_rounds += 1
                if tool_rounds > config.MAX_TOOL_ROUNDS:
                    raise RuntimeError(
                        f"Tool-call limit exceeded ({config.MAX_TOOL_ROUNDS} rounds)"
                    )
                tool_calls = response.choices[0].message.tool_calls
                logger.info("[%s] Model requested %d tool call(s)", trace_id, len(tool_calls))

                # Append the assistant turn (with tool_calls) to the history.
                messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                # Execute each requested tool and append its result.
                for tc in tool_calls:
                    args = json.loads(tc.function.arguments)
                    if not isinstance(args, dict):
                        raise ValueError("Tool arguments must decode to a JSON object")
                    logger.info(
                        "[%s] Calling tool %r with argument_keys=%s",
                        trace_id,
                        tc.function.name,
                        sorted(args),
                    )
                    result = tool_executor(tc.function.name, args)
                    logger.info(
                        "[%s] Tool %r returned result_chars=%d",
                        trace_id,
                        tc.function.name,
                        len(str(result)),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": result,
                    })

                response = _call_with_retry(lambda: _call(messages), trace_id)

        except Exception as exc:
            elapsed = time.perf_counter() - start
            span.set_attribute("error.type", type(exc).__name__)
            span.set_attribute("latency_seconds", elapsed)
            logger.error(
                "[%s] Tool-call request failed after %.2fs — error_type=%s",
                trace_id,
                elapsed,
                type(exc).__name__,
            )
            raise

        elapsed = time.perf_counter() - start
        usage = response.usage
        content = response.choices[0].message.content
        span.set_attribute("latency_seconds", elapsed)
        span.set_attribute("prompt_tokens", usage.prompt_tokens)
        span.set_attribute("completion_tokens", usage.completion_tokens)
        span.set_attribute("total_tokens", usage.total_tokens)
        span.set_attribute("output_chars", len(content or ""))

        logger.info(
            "[%s] Tool-call response — latency=%.2fs prompt_tokens=%s completion_tokens=%s total_tokens=%s output_chars=%d",
            trace_id,
            elapsed,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            len(content or ""),
        )

        return content
