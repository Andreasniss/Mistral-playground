# Agent Guide — Mistral Reliability Lab

Read this file and `TASKS.md` before changing the repository.

## Purpose

This is a compact applied-AI engineering reference for Mistral cloud and local
Ollama models. It demonstrates provider abstraction, controlled tool use, grounded
answers, bounded retries, privacy-first telemetry, and credential-free regression
tests. It is not a production service or a model-quality benchmark.

## Task tracking

Task state lives in `TASKS.md`.

- Move active work to **In Progress** before implementation.
- Move completed work to **Done** after verification.
- Add discovered but unimplemented work to **Backlog**.

## Architecture

| File | Responsibility |
|---|---|
| `config.py` | Environment configuration and runtime validation |
| `llm_client.py` | Provider boundary, retry loop, tool-call loop, telemetry |
| `demo_streamlit.py` | Reviewer-facing UI and application tool allow-list |
| `showcase.py` | Deterministic credential-free preview and retrieval |
| `api.py` | Typed, localhost-only FastAPI surface |
| `evals/` | Versioned deterministic evaluation contract |
| `tests/` | Unit, privacy, and Streamlit interaction tests |
| `RAG/hr_policy.md` | Synthetic grounding document |
| `prompts/` | Version-controlled prompt templates |

## Invariants

1. `config.py` is the only module that reads environment variables.
2. Application surfaces go through `llm_client.chat()` or
   `llm_client.chat_with_tools()`. Capability-specific scripts may use the SDK
   directly only when the shared wrapper does not expose that feature (for example,
   streaming or raw usage comparison), and must say so in their module docstring.
3. Tests and deterministic evals never require credentials or make model calls.
4. Tools are declared with narrow JSON schemas and executed through an explicit
   application allow-list. Never execute a model-provided function name dynamically.
5. Logs and spans contain operational metadata only. Do not record prompts,
   responses, tool arguments, tool results, secrets, or policy content.
6. OpenTelemetry export remains opt-in.
7. Missing cloud credentials fail only when connected mode requests a client;
   imports, CI, and preview mode must remain credential-free.
8. `.env`, logs, virtual environments, and Python caches are never committed.
9. The local policy remains clearly labelled as fictional/synthetic.
10. Do not describe deterministic component checks as model-quality evaluation.

## Development workflow

```bash
uv sync --locked --dev
uv run ruff check .
uv run pytest -q
uv run python -m evals.run_evals
uv run streamlit run demo_streamlit.py
```

CI uses the committed `uv.lock`. Update it with `uv lock` whenever dependencies
change. `requirements.txt` remains as a simple pip-compatible entry point.

## Supported configuration

| Variable | Default | Purpose |
|---|---|---|
| `LLM_BACKEND` | `api` | `api` for Mistral or `local` for Ollama |
| `MISTRAL_API_KEY` | — | Required only for connected Mistral mode |
| `MISTRAL_MODEL` | backend-dependent | Cloud or local model name |
| `MISTRAL_MAX_TOKENS` | `1024` | Maximum generated tokens |
| `MISTRAL_TEMPERATURE` | `0.0` | Sampling temperature |
| `MISTRAL_TOP_P` | unset | Optional nucleus sampling; avoid combining with temperature |
| `REQUEST_TIMEOUT` | `30` | Local-provider request timeout in seconds |
| `RETRY_MAX_ATTEMPTS` | `3` | Total attempts, including the first |
| `RETRY_BASE_DELAY` | `0.5` | Initial retry delay in seconds |
| `RETRY_MAX_DELAY` | `60.0` | Maximum retry delay in seconds |
| `MAX_TOOL_ROUNDS` | `4` | Maximum model/tool cycles per request |
| `OTEL_ENABLED` | `false` | Opt in to trace export |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP/gRPC endpoint |
| `API_KEY` | — | Protects local FastAPI model endpoints |

## Extension rules

- Put reusable prompts in `prompts/*.txt` and load them with `load_prompt()`.
- Add a test for each new routing, retry, privacy, tool, or configuration behavior.
- Add or update a versioned eval case when changing preview routing or grounding.
- Keep public claims tied to code or automated evidence.
- Document production gaps in `SECURITY.md`; do not silently broaden this demo's
  security or reliability claims.
