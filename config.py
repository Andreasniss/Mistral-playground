import os
import logging
from dotenv import load_dotenv

# Load variables from .env into the environment before reading them.
# Has no effect if .env does not exist (e.g. in CI where vars are injected directly).
load_dotenv()

# --- Mistral API ---
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
# "latest" aliases always point to the current recommended version of each tier.
# Use a pinned ID (e.g. "mistral-large-2512") if you need output stability across deployments.
# Full model list: https://docs.mistral.ai/getting-started/models/models_overview/
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
MISTRAL_MAX_TOKENS = int(os.getenv("MISTRAL_MAX_TOKENS", "1024"))
# Mistral docs recommend temperature in the range 0.0–0.7.
# Do not set both temperature and top_p at the same time.
# https://docs.mistral.ai/capabilities/completion/
MISTRAL_TEMPERATURE = float(os.getenv("MISTRAL_TEMPERATURE", "0.7"))
REQUEST_TIMEOUT = 30  # seconds

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

if not MISTRAL_API_KEY:
    raise EnvironmentError("MISTRAL_API_KEY is not set. Copy .env.example to .env and fill in your key.")
