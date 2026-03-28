# Mistral Playground

A structured Python playground for testing the Mistral API, following LLM project best practices.

---

## Project Structure

```
Mistral-playground/
├── .env                  # 🔒 secrets — NEVER commit (create from .env.example)
├── .env.example          # template with placeholder values — safe to commit
├── .gitignore            # excludes .env and other generated files
├── config.py             # loads and validates env vars (model, params, key)
├── llm_client.py         # single Mistral API wrapper with a chat() function
├── prompts_loader.py     # utility to load prompt files from prompts/
├── main.py               # demo application using the above modules
├── requirements.txt      # project dependencies
├── prompts/
│   ├── system_prompt.txt # default system prompt
│   └── summarize.txt     # summarization prompt with {{TEXT}} placeholder
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
MISTRAL_TEMPERATURE=0.7
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

### 6. Tests — `tests/test_main.py`

Tests use `unittest.mock` to patch `get_client()`, so they run without an API key and without making real network calls. This makes the test suite fast and safe to run in CI. Four tests cover:

- `chat()` sends the correct user message
- `chat()` includes a system message when provided
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

## Extending the Playground

- **Add a new prompt**: create a `.txt` file in `prompts/` and load it with `load_prompt("your_file.txt")`
- **Change the model**: update `MISTRAL_MODEL` in `.env` — no code changes needed
- **Add a new use case**: write a function in `main.py` that calls `chat()` with your prompt
- **Stream responses**: the Mistral SDK supports `client.chat.stream()` — swap `chat.complete` in `llm_client.py`
