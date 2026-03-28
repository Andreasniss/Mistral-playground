from mistralai import Mistral
import config


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
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": user_message})

    response = get_client().chat.complete(
        model=model or config.MISTRAL_MODEL,
        messages=messages,
        max_tokens=max_tokens or config.MISTRAL_MAX_TOKENS,
        temperature=temperature if temperature is not None else config.MISTRAL_TEMPERATURE,
    )
    return response.choices[0].message.content
