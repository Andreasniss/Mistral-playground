import time
import uuid
import random
from typing import Optional
from mistralai import Mistral
import config
from logger import get_logger

logger = get_logger("llm_client")

# Singleton Mistral client — created once and reused across calls so the SDK
# does not re-initialise on every request.
_client = None

# Status codes worth retrying, per Mistral API docs:
# 429 — rate limit exceeded (slow down and try again)
# 500/502/503/504 — transient server-side errors
# Do NOT retry 4xx client errors (401 bad key, 422 bad payload) — those won't
# resolve by themselves and retrying wastes quota.
# https://docs.mistral.ai/api/
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def get_client() -> Mistral:
    """Return the shared Mistral SDK client, creating it on first call."""
    global _client
    if _client is None:
        _client = Mistral(api_key=config.MISTRAL_API_KEY)
    return _client


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception represents a transient, retryable error."""
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status in _RETRYABLE_STATUS_CODES
    # Fallback: some SDK versions embed the status code in the message string
    # rather than exposing it as an attribute.
    return any(str(code) in str(exc) for code in _RETRYABLE_STATUS_CODES)


def _get_retry_after(exc: Exception) -> Optional[float]:
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
                "[%s] Retryable error (%s), attempt %d/%d — retrying in %.1fs%s",
                trace_id,
                exc,
                attempt + 1,
                config.RETRY_MAX_ATTEMPTS,
                delay,
                " (Retry-After header)" if retry_after is not None else "",
            )
            time.sleep(delay)
    raise last_exc


def chat(
    user_message: str,
    system_message: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """Send a chat message to Mistral and return the assistant reply as a string.

    Args:
        user_message:   The user turn to send.
        system_message: Optional system prompt to prepend (sets assistant behaviour).
        model:          Override the model from config (e.g. "mistral-small-latest").
        max_tokens:     Override the token limit from config.
        temperature:    Override the sampling temperature from config (0.0–0.7).

    Returns:
        The assistant's reply as a plain string.

    Raises:
        Exception: Re-raises any API error after all retry attempts are exhausted.
    """
    # Short random ID attached to every log line for this call so request and
    # response entries can be correlated in the log file.
    trace_id = uuid.uuid4().hex[:8]
    resolved_model = model or config.MISTRAL_MODEL

    # Build the messages array. System message must come first if present.
    # Valid roles: "system", "user", "assistant", "tool"
    # https://docs.mistral.ai/capabilities/completion/
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": user_message})

    logger.info(
        "[%s] Request — model=%s max_tokens=%s temperature=%s user_message=%.80r",
        trace_id,
        resolved_model,
        max_tokens or config.MISTRAL_MAX_TOKENS,
        temperature if temperature is not None else config.MISTRAL_TEMPERATURE,
        user_message,
    )

    start = time.perf_counter()
    try:
        response = _call_with_retry(
            lambda: get_client().chat.complete(
                model=resolved_model,
                messages=messages,
                max_tokens=max_tokens or config.MISTRAL_MAX_TOKENS,
                temperature=temperature if temperature is not None else config.MISTRAL_TEMPERATURE,
            ),
            trace_id,
        )
    except Exception as exc:
        logger.error("[%s] Request failed after %.2fs — %s", trace_id, time.perf_counter() - start, exc)
        raise

    elapsed = time.perf_counter() - start
    # The usage object contains prompt_tokens, completion_tokens, total_tokens —
    # the primary signal for tracking cost and latency, as recommended by Mistral docs.
    usage = response.usage
    content = response.choices[0].message.content

    logger.info(
        "[%s] Response — latency=%.2fs prompt_tokens=%s completion_tokens=%s total_tokens=%s",
        trace_id,
        elapsed,
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.total_tokens,
    )
    logger.debug("[%s] Response content: %.120r", trace_id, content)

    return content
