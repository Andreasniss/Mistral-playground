from typing import Optional
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

import config
import llm_client
import prompts_loader
from logger import get_logger

logger = get_logger("api")

app = FastAPI(
    title="Mistral Playground API",
    version="1.0.0",
    description="Local HTTP wrapper around the Mistral API. Requires X-API-Key header on protected endpoints.",
)

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _verify_api_key(api_key: str = Security(_API_KEY_HEADER)) -> str:
    """Dependency that validates the X-API-Key header against API_KEY in .env."""
    if not config.API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY is not configured on the server")
    if api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")
    return api_key


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    system: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    model: str


class SummarizeRequest(BaseModel):
    text: str


class SummarizeResponse(BaseModel):
    summary: str
    model: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", summary="Liveness check — no auth required")
def health():
    """Returns server status and the configured Mistral model."""
    return {"status": "ok", "model": config.MISTRAL_MODEL}


@app.post("/chat", response_model=ChatResponse, summary="Send a chat message to Mistral")
def chat(req: ChatRequest, _: str = Depends(_verify_api_key)):
    """
    Send a user message and receive the assistant reply.

    - **message**: the user turn to send
    - **system**: optional system prompt (overrides the default behaviour)
    """
    try:
        reply = llm_client.chat(req.message, system_message=req.system)
    except Exception as exc:
        logger.error("POST /chat failed: %s", exc)
        raise HTTPException(status_code=502, detail="Mistral API error — check logs for details")
    return ChatResponse(reply=reply, model=config.MISTRAL_MODEL)


@app.post("/summarize", response_model=SummarizeResponse, summary="Summarise text using the built-in prompt template")
def summarize(req: SummarizeRequest, _: str = Depends(_verify_api_key)):
    """
    Summarise the supplied text using the `prompts/summarize.txt` template.

    - **text**: the content to summarise
    """
    template = prompts_loader.load_prompt("summarize.txt")
    prompt = template.replace("{{TEXT}}", req.text)
    try:
        summary = llm_client.chat(prompt)
    except Exception as exc:
        logger.error("POST /summarize failed: %s", exc)
        raise HTTPException(status_code=502, detail="Mistral API error — check logs for details")
    return SummarizeResponse(summary=summary, model=config.MISTRAL_MODEL)
