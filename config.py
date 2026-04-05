import os
import logging
from dotenv import load_dotenv

# Load variables from .env into the environment before reading them.
# Has no effect if .env does not exist (e.g. in CI where vars are injected directly).
load_dotenv()

# --- Backend selection ---
# "api"   — Mistral cloud API (requires MISTRAL_API_KEY)
# "local" — local Ollama server (requires Ollama running at OLLAMA_BASE_URL)
LLM_BACKEND = os.getenv("LLM_BACKEND", "api").lower()

# --- Mistral API ---
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# "latest" aliases always point to the current recommended version of each tier.
# Use a pinned ID (e.g. "mistral-large-2512") if you need output stability across deployments.
# Full model list: https://docs.mistral.ai/getting-started/models/models_overview/
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest" if LLM_BACKEND == "api" else "mistral")
MISTRAL_MAX_TOKENS = int(os.getenv("MISTRAL_MAX_TOKENS", "1024"))
# Mistral docs recommend temperature in the range 0.0–0.7.
# Do not set both temperature and top_p at the same time — use one or the other.
# https://docs.mistral.ai/capabilities/completion/
MISTRAL_TEMPERATURE = float(os.getenv("MISTRAL_TEMPERATURE", "0.0"))
# top_p (nucleus sampling): only used when MISTRAL_TEMPERATURE is not set (i.e. set to None).
# Range 0.0–1.0 — e.g. 0.9 means sample from the top 90% of the probability mass.
MISTRAL_TOP_P = os.getenv("MISTRAL_TOP_P")  # None by default — not sent unless explicitly set
if MISTRAL_TOP_P is not None:
    MISTRAL_TOP_P = float(MISTRAL_TOP_P)
REQUEST_TIMEOUT = 30  # seconds

# --- Local Ollama ---
# Base URL for the Ollama server. Default matches `ollama serve` with no config.
# Only used when LLM_BACKEND=local.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# --- Logging ---
# Controls console verbosity. The log file always captures DEBUG regardless of this setting.
# Valid values: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

# --- Retry ---
# Per Mistral docs, retry 429 (rate limit) and 5xx (server) errors with exponential backoff.
# https://docs.mistral.ai/api/
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))   # total attempts including the first
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "0.5"))   # seconds before first retry
RETRY_MAX_DELAY = float(os.getenv("RETRY_MAX_DELAY", "60.0"))    # cap on any single delay

# --- API server ---
# Secret used to authenticate requests to the FastAPI server (X-API-Key header).
# Only required when running api.py — not needed for plain python main.py usage.
# Generate a strong value with: python -c "import secrets; print(secrets.token_hex(32))"
API_KEY = os.getenv("API_KEY")

if LLM_BACKEND == "api" and not MISTRAL_API_KEY:
    raise EnvironmentError(
        "MISTRAL_API_KEY is not set. Copy .env.example to .env and fill in your key.\n"
        "To run locally without an API key, set LLM_BACKEND=local in your .env."
    )
