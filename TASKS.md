# TASKS.md

In-flight and backlog items for this repo. When something becomes a real commitment, it also gets a due date in Todoist.

---

## In Progress

<!-- Add items here when you start working on them -->

---

## Backlog

### Observability
- [ ] Prometheus metrics — add `prometheus-client` instrumentation to `llm_client.py` (latency histogram, error counter, token usage gauge); add Grafana dashboard config
- [ ] Langfuse integration — per-request traces, cost tracking, prompt versioning (`mlflow.mistral.autolog()` alternative)
- [ ] MLflow tracing — one-line `mlflow.mistral.autolog()` setup + experiment tracking

### API / Backend
- [ ] Async endpoints in `api.py` — swap blocking `chat()` calls for `client.chat.complete_async()` to support concurrent requests

### RAG
- [ ] Expand RAG demo beyond `hr_policy.md` — add chunking strategy comparison (fixed-size vs. sentence vs. semantic), evaluate retrieval quality

### Models / Capabilities
- [ ] Structured JSON output demo — use `response_format` with a Pydantic model, add as a section in `demo.ipynb`
- [ ] `random_seed` reproducibility demo — show deterministic outputs for the same prompt across runs
- [ ] `safe_prompt` / content moderation demo — test guardrailing with and without system prompt

### Developer Experience
- [ ] Add `MISTRAL_MODEL` to the Quick Start `.env` example (currently only shows `MISTRAL_API_KEY`)
- [ ] Pre-commit hook for `ruff` / `black` linting

---

## Done

- [x] Streamlit web demo with weather tool integration
- [x] OpenTelemetry tracing with Jaeger
- [x] FastAPI server with `X-API-Key` auth and `/health`, `/chat`, `/summarize` endpoints
- [x] Ollama local backend (`LLM_BACKEND=local`)
- [x] Retry with exponential backoff + `Retry-After` header support
- [x] `demo.ipynb` — 19-section interactive notebook
- [x] Function / tool calling with Open-Meteo weather demo
- [x] Streaming tokens demo (`demo_stream.py`)
- [x] Model comparison demo (`demo_compare.py`)
- [x] Tests with mocks — 12 test cases, no API key needed
