import time
import uuid
import random
from mistralai import Mistral
import config
from logger import get_logger

logger = get_logger("llm_client")

_client = None
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def get_client() -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=config.MISTRAL_API_KEY)
    return _client


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status in _RETRYABLE_STATUS_CODES
    # fallback for SDKs that embed the status code in the message
    return any(str(code) in str(exc) for code in _RETRYABLE_STATUS_CODES)


def _call_with_retry(fn, trace_id: str):
    last_exc = None
    for attempt in range(config.RETRY_MAX_ATTEMPTS):
        try:
            return fn()
        except Exception as exc:
            if not _is_retryable(exc):
                raise
            last_exc = exc
            if attempt == config.RETRY_MAX_ATTEMPTS - 1:
                break
            delay = min(
                config.RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5),
                config.RETRY_MAX_DELAY,
            )
            logger.warning(
                "[%s] Retryable error (%s), attempt %d/%d — retrying in %.1fs",
                trace_id,
                exc,
                attempt + 1,
                config.RETRY_MAX_ATTEMPTS,
                delay,
            )
            time.sleep(delay)
    raise last_exc


def chat(
    user_message: str,
    system_message: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    trace_id = uuid.uuid4().hex[:8]
    resolved_model = model or config.MISTRAL_MODEL

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
