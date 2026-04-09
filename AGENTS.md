# Agent Guide — Mistral-playground

This file is the single reference for any coding agent (Claude Code, Vibestral, Devstral, Cursor, etc.) working in this repo. Read it before making changes.

---

## What This Repo Is

A structured Python playground for the Mistral AI API that demonstrates production-grade patterns: centralised config, dual-handler logging, a singleton API client, prompt file management, retry with exponential backoff, and fully mocked unit tests.

It is intentionally minimal — a foundation to extend, not a finished product.

---

## File Map

```
Mistral-playground/
├── config.py           # loads + validates all env vars — single source of truth for settings
├── logger.py           # get_logger(name) — console handler + file handler
├── llm_client.py       # chat() — the only public API entry point; get_client() singleton
├── prompts_loader.py   # load_prompt(filename) — reads .txt files from prompts/
├── main.py             # run_basic_chat(), run_summarize() — wires modules together
├── demo.ipynb          # interactive notebook demonstrating every module
├── prompts/
│   ├── system_prompt.txt
│   └── summarize.txt   # uses {{TEXT}} placeholder
├── tests/
│   └── test_main.py    # 12 unit tests — all mocked, no real API calls
├── .env.example        # safe template — committed
├── .env                # real secrets — NEVER committed (gitignored)
└── requirements.txt    # mistralai>=2.0.0, python-dotenv>=1.0.0, pytest>=8.0.0
```

---

## Architecture & Invariants

Keep these patterns intact when modifying the repo.

### 1. `config.py` is the only place that reads env vars

All other modules import from `config`, never call `os.getenv` themselves.
`config.py` raises `EnvironmentError` at import time if `MISTRAL_API_KEY` is missing.

### 2. `chat()` in `llm_client.py` is the only public API surface

All Mistral API calls go through `chat()`. Do not call `get_client().chat.complete()` directly in application code — that bypasses retry logic and logging.

### 3. Singleton client — `get_client()`

`_client` is a module-level variable. `get_client()` creates it once on first call. Do not reset or replace `_client` outside of tests.

### 4. Prompts live in `prompts/` as `.txt` files

Do not hardcode prompt strings in Python. Add a `.txt` file and use `load_prompt()`.
Use `{{PLACEHOLDER}}` for template variables (double braces — no collision with f-strings).

### 5. Tests must not make real API calls

All tests in `tests/` mock `get_client()` via `unittest.mock.patch`. If you add tests, follow this pattern. No test should require `MISTRAL_API_KEY` to be set.

### 6. Never commit `.env`

It is in `.gitignore`. Update `.env.example` if you add new env vars.

---

## Environment Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in MISTRAL_API_KEY
```

### All supported env vars

| Variable | Default | Purpose |
|---|---|---|
| `MISTRAL_API_KEY` | — | **Required.** Get from console.mistral.ai |
| `MISTRAL_MODEL` | `mistral-large-latest` | Model alias or pinned ID |
| `MISTRAL_MAX_TOKENS` | `1024` | Default token limit per call |
| `MISTRAL_TEMPERATURE` | `0.0` | Sampling temperature (0.0 = deterministic, recommended for testing) |
| `LOG_LEVEL` | `INFO` | Console log verbosity (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `RETRY_MAX_ATTEMPTS` | `3` | Total attempts including the first |
| `RETRY_BASE_DELAY` | `0.5` | Seconds before first retry |
| `RETRY_MAX_DELAY` | `60.0` | Cap on any single delay |

---

## Running the Code

```bash
python main.py          # run the two demos (requires MISTRAL_API_KEY)
pytest tests/           # run all tests (no API key needed)
jupyter notebook demo.ipynb   # interactive walkthrough
```

---

## How to Extend

### Add a new prompt

1. Create `prompts/your_prompt.txt`
2. Use `{{PLACEHOLDER}}` for any dynamic values
3. Load with `load_prompt("your_prompt.txt")` and fill with `.replace()`

### Add a new use case

Write a function in `main.py` that calls `chat()`. Import `load_prompt` for any prompt files.

```python
def run_my_feature(input_text: str):
    template = load_prompt("my_prompt.txt")
    prompt = template.replace("{{INPUT}}", input_text)
    response = chat(prompt, system_message=load_prompt("system_prompt.txt"))
    print(response)
```

### Override model / params per call

```python
chat(
    user_message="...",
    model="mistral-small-latest",   # cheaper/faster for simple tasks
    temperature=0.0,                 # deterministic output
    max_tokens=100,                  # short reply
)
```

### Add a new env var

1. Add it to `.env.example` with a placeholder value and comment
2. Read and type-coerce it in `config.py`
3. Use `config.YOUR_VAR` everywhere else

---

## Key Patterns Reference

### Retry logic (`llm_client.py`)

Retries on: `429, 500, 502, 503, 504`
Does NOT retry: `4xx` client errors (they won't self-resolve)
Delay formula: `min(base_delay × 2^attempt + jitter(0–0.5s), max_delay)`
If server sends `Retry-After` header, that value is used instead.

### Logging

Each `chat()` call generates a short random `trace_id` (e.g. `a3f9c21b`).
Every log line for that call carries the same `trace_id` — grep for it to see the full lifecycle.

Console level: controlled by `LOG_LEVEL` in `.env`
File level: always `DEBUG` → `logs/app.log`

### Message roles

System message (if provided) must come before the user message in the array.
Valid roles: `system`, `user`, `assistant`, `tool`

---

## What NOT to Do

- Do not call `os.getenv()` outside `config.py`
- Do not import from `mistralai` directly in `main.py` — use `llm_client.chat()`
- Do not hardcode model names outside `config.py` (except per-call overrides for demos)
- Do not add `print()` statements to library modules (`config`, `logger`, `llm_client`, `prompts_loader`) — use the logger
- Do not write to `logs/` manually — the logger handles it
- Do not commit `.env`, `logs/`, or `__pycache__/`
