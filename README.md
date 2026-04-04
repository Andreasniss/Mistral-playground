# Mistral Playground

A structured Python playground for testing the Mistral API, following LLM project best practices.

---

## Project Structure

```
Mistral-playground/
├── .env                  # 🔒 secrets — NEVER commit (create from .env.example)
├── .env.example          # template with placeholder values — safe to commit
├── .gitignore            # excludes .env, logs/, and other generated files
├── config.py             # loads and validates env vars (model, params, key, log level)
├── logger.py             # configures logging to stdout and logs/app.log
├── llm_client.py         # single Mistral API wrapper with tracing and logging
├── prompts_loader.py     # utility to load prompt files from prompts/
├── main.py               # demo application using the above modules
├── api.py                # FastAPI server — exposes /health, /chat, /summarize
├── requirements.txt      # project dependencies
├── prompts/
│   ├── system_prompt.txt # default system prompt
│   └── summarize.txt     # summarization prompt with {{TEXT}} placeholder
├── logs/                 # auto-created at runtime — gitignored
│   └── app.log
└── tests/
    └── test_main.py      # unit tests using mocks (no real API calls)
```

---

## How It Was Set Up

### 1. Secrets management — `.env` + `.gitignore`

The first priority is keeping the API key out of git. `.env` holds the real key locally and is listed in `.gitignore` so it can never be accidentally committed. `.env.example` is a safe placeholder that is committed so others know what variables to set.

```
MISTRAL_API_KEY=your_mistral_api_key_here
MISTRAL_MODEL=mistral-large-latest
MISTRAL_MAX_TOKENS=1024
MISTRAL_TEMPERATURE=0.0
```

### 2. Centralised config — `config.py`

All settings are loaded once at import time using `python-dotenv`. If `MISTRAL_API_KEY` is missing, the module raises an `EnvironmentError` immediately — failing fast rather than producing a confusing error later.

```python
load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise EnvironmentError("MISTRAL_API_KEY is not set.")
```

### 3. Single API wrapper — `llm_client.py`

All Mistral API calls go through one place. A singleton pattern (`get_client()`) means the SDK client is created once and reused, avoiding repeated initialisation. The `chat()` function has a clean interface — just pass a message and optionally a system prompt, model override, or parameter overrides.

```python
def chat(user_message, system_message=None, model=None, max_tokens=None, temperature=None) -> str:
    ...
```

This means if the underlying SDK changes, only one file needs updating.

### 4. Prompt templates — `prompts/` + `prompts_loader.py`

Prompts are stored as plain `.txt` files rather than hardcoded strings. This keeps them easy to edit without touching Python code. `prompts_loader.py` provides a single `load_prompt(filename)` function that resolves paths relative to the project root, so it works regardless of where the script is run from.

The `summarize.txt` prompt uses a `{{TEXT}}` placeholder that `main.py` fills in with `.replace()`.

### 5. Application logic — `main.py`

`main.py` wires everything together and shows two usage patterns:

- **Basic chat**: loads the system prompt, sends a hardcoded user message
- **Summarize**: loads the summarize template, injects text, calls the API

This separation means the modules (`llm_client`, `prompts_loader`, `config`) are independently reusable.

### 6. Logging — `logger.py`

A single `get_logger(name)` function configures and returns a named logger. Every logger gets two handlers:

- **Console** (`stdout`): respects `LOG_LEVEL` from `.env` — set to `WARNING` to silence it in production
- **File** (`logs/app.log`): always set to `DEBUG` so the full detail is captured on disk regardless of the console level

The `logs/` directory is created automatically at runtime and is excluded from git.

```
LOG_LEVEL=INFO   # change to DEBUG, WARNING, ERROR as needed
```

### 7. Tracing — `llm_client.py`

Each call to `chat()` gets a short random **trace ID** (e.g. `[a3f9c21b]`) that appears on every log line for that call, making it easy to correlate request and response entries in the log file.

What is logged per call:

| Event | Level | Fields |
|---|---|---|
| Request | INFO | trace ID, model, max_tokens, temperature, user message (truncated) |
| Response | INFO | trace ID, latency (s), prompt_tokens, completion_tokens, total_tokens |
| Response content | DEBUG | trace ID, content (truncated) |
| API error | ERROR | trace ID, latency, exception message |

Example log output:

```
2024-01-15 10:23:41 [INFO] llm_client — [a3f9c21b] Request — model=mistral-large-latest max_tokens=1024 temperature=0.0 user_message='Explain what Mistral AI is...'
2024-01-15 10:23:43 [INFO] llm_client — [a3f9c21b] Response — latency=1.84s prompt_tokens=42 completion_tokens=87 total_tokens=129
```

### 8. Retry with exponential backoff — `llm_client.py`

The [Mistral API docs](https://docs.mistral.ai/api/) recommend retrying `429` (rate limit) and `5xx` (server) errors with exponential backoff and jitter. A `_call_with_retry()` helper wraps every API call:

- Retries on status codes `429, 500, 502, 503, 504`
- Does **not** retry `4xx` client errors (bad request, auth failure, etc.) — those won't resolve by retrying
- If the server returns a `Retry-After` header on a 429, that value is used as the delay instead of the calculated one
- Delay formula (when no `Retry-After` header): `base_delay × 2^attempt + random jitter (0–0.5s)`, capped at `max_delay`
- Logs a `WARNING` on each retry attempt (noting if `Retry-After` was honoured), `ERROR` if all attempts are exhausted

```
RETRY_MAX_ATTEMPTS=3    # total attempts (1 original + 2 retries)
RETRY_BASE_DELAY=0.5    # seconds — first retry waits ~0.5s
RETRY_MAX_DELAY=60.0    # seconds — cap for any single delay
```

Example log when a 429 with a `Retry-After` header is hit and recovered:

```
[a3f9c21b] Retryable error (HTTP 429), attempt 1/3 — retrying in 5.0s (Retry-After header)
[a3f9c21b] Response — latency=6.84s prompt_tokens=42 completion_tokens=87 total_tokens=129
```

### 9. Tests — `tests/test_main.py`

Tests use `unittest.mock` to patch `get_client()`, so they run without an API key and without making real network calls. This makes the test suite fast and safe to run in CI. Eleven tests cover:

- `chat()` sends the correct user message
- `chat()` includes a system message when provided
- Retry succeeds after a transient 429
- Retry exhaustion raises the last exception after `RETRY_MAX_ATTEMPTS` attempts
- Non-retryable errors (e.g. 400) raise immediately with no sleep
- `Retry-After` header value is used as the sleep duration when present
- Retry delays are exponential and never exceed `RETRY_MAX_DELAY`
- `chat()` logs a `WARNING` on retry attempts
- `chat()` logs request and response fields (including latency and token counts)
- `chat()` logs an error and re-raises on API failure
- `load_prompt()` returns file contents correctly
- `load_prompt()` raises `FileNotFoundError` for missing files

---

## Getting Started

**1. Clone and install dependencies**

```bash
git clone https://github.com/Andreasniss/Mistral-playground
cd Mistral-playground
pip install -r requirements.txt
```

**2. Create your `.env` file**

```bash
cp .env.example .env
```

Then open `.env` and replace `your_mistral_api_key_here` with your actual key from [console.mistral.ai](https://console.mistral.ai).

**3. Run the demo**

```bash
python main.py
```

**4. Run the tests** (no API key needed)

```bash
pytest tests/
```

---

## FastAPI Server

The project includes a local HTTP API built with FastAPI (`api.py`). It exposes the same `chat()` and `summarize()` functionality over HTTP, making it easy to call from any tool — curl, Postman, a frontend, another service — without writing Python.

### Why FastAPI was added

- **Interactive docs**: FastAPI auto-generates a `/docs` UI (Swagger) at startup. You can test every endpoint in the browser with no extra tooling.
- **Typed contracts**: Pydantic models validate every request and response, so malformed input is rejected with a clear `422` before it reaches the Mistral API.
- **Async-ready**: FastAPI is built on async Python, which pairs well with `client.chat.complete_async()` for concurrent requests if you extend this later.
- **Zero rewrite**: `llm_client.py`, `prompts_loader.py`, `config.py`, and `logger.py` are all unchanged — `api.py` simply wraps them.

### Security design

- **Localhost-only**: the server binds to `127.0.0.1`, so it is never reachable from the network — only from your own machine.
- **`X-API-Key` header**: every protected endpoint requires this header. The value must match `API_KEY` in your `.env`. If missing or wrong, the server returns `401`. This prevents other local processes from hitting the server without the key.
- **`/health` is unauthenticated**: safe for liveness checks without exposing a credential.

### Setup

Add `API_KEY` to your `.env`:

```bash
# Generate a strong random key
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output as the value:

```
API_KEY=your_generated_key_here
```

### Start the server

```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```

The server is now running at `http://127.0.0.1:8000`.

### Demo the endpoints

**Open the interactive docs** in your browser:

```
http://127.0.0.1:8000/docs
```

Every endpoint is listed with its schema. Click **Try it out** on `/chat` or `/summarize`, add your `X-API-Key` via the **Authorize** button (top right), and send a real request.

**Or use curl:**

```bash
# Health check — no auth needed
curl http://127.0.0.1:8000/health

# Chat
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_generated_key_here" \
  -d '{"message": "Explain transformers in one sentence"}'

# Summarise
curl -X POST http://127.0.0.1:8000/summarize \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_generated_key_here" \
  -d '{"text": "Large language models are neural networks trained on vast amounts of text..."}'
```

### Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Liveness check — returns status and model name |
| `POST` | `/chat` | `X-API-Key` | Send a message; optional `system` field to set behaviour |
| `POST` | `/summarize` | `X-API-Key` | Summarise text using the `prompts/summarize.txt` template |

---

## Extending the Playground

- **Add a new prompt**: create a `.txt` file in `prompts/` and load it with `load_prompt("your_file.txt")`
- **Change the model**: update `MISTRAL_MODEL` in `.env` — no code changes needed. See the [full model list](https://docs.mistral.ai/getting-started/models/models_overview/)
- **Add a new use case**: write a function in `main.py` that calls `chat()` with your prompt
- **Quiet the console**: set `LOG_LEVEL=WARNING` in `.env` — errors still appear but request/response logs are suppressed
- **Read the full log**: `cat logs/app.log` — always written at `DEBUG` level regardless of `LOG_LEVEL`
- **Tune retry behaviour**: adjust `RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY`, `RETRY_MAX_DELAY` in `.env`

---

## Next Steps to Explore

These are not implemented in the playground yet but are worth knowing about and experimenting with.

### Streaming responses
Instead of waiting for the full reply, stream tokens as they are generated. Useful for chat UIs and long outputs.
→ [Streaming guide](https://docs.mistral.ai/capabilities/completion/) — swap `chat.complete` for `chat.stream` in `llm_client.py`

### Reproducible outputs with `random_seed`
Pass `random_seed=42` (integer) to `client.chat.complete()` to get deterministic outputs for the same input. Useful for testing and benchmarking.
→ [API reference](https://docs.mistral.ai/api/)

### Content moderation with `safe_prompt`
Pass `safe_prompt=True` to enable Mistral's built-in guardrailing against sensitive content. Can be combined with your own system prompt.
→ [Guardrailing guide](https://docs.mistral.ai/capabilities/guardrailing/)

### Structured / JSON output
Use `response_format` with a JSON schema or Pydantic model to get typed, structured responses instead of free-form text.
→ [Structured output guide](https://docs.mistral.ai/capabilities/structured-output/custom_structured_output/)

### Function / tool calling
Let the model call your Python functions. Pass a `tools` list to `chat.complete()` and handle `finish_reason == "tool_calls"` in the response.
→ [Function calling guide](https://docs.mistral.ai/capabilities/function_calling/)

### Observability integrations
The `usage` object we already log (token counts) is the baseline signal. For richer dashboards, traces, and cost tracking, the official integrations are:

| Tool | What it gives you | Official guide |
|---|---|---|
| **Langfuse** | Per-request traces, latency histograms, cost tracking, prompt versioning | [Langfuse + Mistral cookbook](https://docs.mistral.ai/cookbooks/third_party-langfuse-cookbook_langfuse_mistral_sdk_integration) |
| **MLflow** | Auto-logging with one line (`mlflow.mistral.autolog()`), experiment tracking, model registry | [MLflow tracing guide](https://docs.mistral.ai/cookbooks/third_party-mlflow-mistral-mlflow-tracing) |
| **Langtrace** | Open-source OpenTelemetry-based tracing for LLM calls | [Langtrace docs](https://docs.langtrace.ai) |

### Async calls
For concurrent requests or use inside an async framework (FastAPI, etc.), use the async variant:
```python
async with Mistral(api_key=...) as client:
    response = await client.chat.complete_async(model=..., messages=[...])
```
→ [SDK clients reference](https://docs.mistral.ai/getting-started/clients/)
