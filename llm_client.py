import time
import uuid
from mistralai import Mistral
import config
from logger import get_logger

logger = get_logger("llm_client")

_client = None


def get_client() -> Mistral:
    global _client
    if _client is None:
        _client = Mistral(api_key=config.MISTRAL_API_KEY)
    return _client


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
        response = get_client().chat.complete(
            model=resolved_model,
            messages=messages,
            max_tokens=max_tokens or config.MISTRAL_MAX_TOKENS,
            temperature=temperature if temperature is not None else config.MISTRAL_TEMPERATURE,
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
