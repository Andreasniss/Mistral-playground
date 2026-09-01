"""Public Streamlit experience for the Agent Reliability Lab."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

import streamlit as st

import config
from llm_client import chat_with_tools
from prompts_loader import load_prompt
from showcase import run_showcase

try:
    from opentelemetry import trace
    from opentelemetry.instrumentation.streamlit import StreamlitInstrumentor

    if config.OTEL_ENABLED:
        StreamlitInstrumentor().instrument()
    _tracer = trace.get_tracer(__name__)
except ImportError:  # pragma: no cover - optional instrumentation
    _tracer = None


def trace_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Record metadata only. Prompts, responses, and tool payloads stay private."""
    if not config.OTEL_ENABLED or _tracer is None:
        return
    with _tracer.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            span.set_attribute(key, str(value))


def _geocode(city: str) -> tuple[float, float, str]:
    params = urllib.parse.urlencode({"name": city, "count": 1, "language": "en", "format": "json"})
    with urllib.request.urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{params}", timeout=10) as response:
        data = json.loads(response.read())
    if not data.get("results"):
        raise ValueError(f"City not found: {city!r}")
    result = data["results"][0]
    return result["latitude"], result["longitude"], f"{result['name']}, {result.get('country', '')}"


def get_current_weather(location: str, format: str = "celsius") -> str:
    city = location.split(",")[0].strip()
    latitude, longitude, resolved_name = _geocode(city)
    unit = "celsius" if format == "celsius" else "fahrenheit"
    params = urllib.parse.urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "temperature_unit": unit,
        "wind_speed_unit": "kmh",
        "forecast_days": 1,
    })
    with urllib.request.urlopen(f"https://api.open-meteo.com/v1/forecast?{params}", timeout=10) as response:
        current = json.loads(response.read())["current"]
    return json.dumps({
        "location": resolved_name,
        "temperature": current["temperature_2m"],
        "temperature_unit": "°C" if unit == "celsius" else "°F",
        "feels_like": current["apparent_temperature"],
        "wind_speed_kmh": current["wind_speed_10m"],
        "weather_code": current["weather_code"],
    })


def get_policy_information(query: str) -> str:
    """Return the local policy document; the model extracts only relevant evidence."""
    policy = (config.PROJECT_ROOT / "RAG" / "hr_policy.md").read_text(encoding="utf-8")
    return json.dumps({"query": query, "document": policy})


def execute_tool(name: str, args: dict[str, Any]) -> str:
    allowed = {"get_current_weather": get_current_weather, "search_policy": get_policy_information}
    if name not in allowed:
        raise ValueError(f"Tool is not allow-listed: {name}")
    return allowed[name](**args)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get current weather for a city from Open-Meteo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City and country"},
                    "format": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location", "format"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "Search the fictional Acme employee policy for a grounded answer.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


def connected_mode() -> bool:
    if config.LLM_BACKEND == "local":
        return True
    return config.MISTRAL_API_KEY not in {None, "", "your_mistral_api_key_here"}


def _history_for_model() -> list[dict[str, str]]:
    return [
        {"role": item["role"], "content": item["content"]}
        for item in st.session_state.messages[-8:]
        if item["role"] in {"user", "assistant"}
    ]


def _styles() -> None:
    st.markdown(
        """
        <style>
          .stApp { background: radial-gradient(circle at 75% 0%, #2b1a14 0, #101114 32rem); }
          .block-container { max-width: 1120px; padding-top: 2.3rem; }
          .eyebrow { color:#ff8a5b; font-size:.78rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
          .hero-title { font-size:clamp(2.3rem,5vw,4.5rem); line-height:1.02; letter-spacing:-.045em; margin:.55rem 0 1rem; }
          .hero-copy { color:#b8bbc3; font-size:1.08rem; max-width:760px; line-height:1.65; }
          .proof-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:.75rem; margin:1.6rem 0 1.4rem; }
          .proof { border:1px solid #30333b; background:#181a1f; border-radius:14px; padding:1rem; }
          .proof strong { display:block; color:#fafafa; margin-bottom:.25rem; }
          .proof span { color:#8f949f; font-size:.82rem; }
          .mode { display:inline-flex; gap:.45rem; align-items:center; border:1px solid #3a3d46; border-radius:999px; padding:.35rem .7rem; color:#c8cbd2; font-size:.8rem; }
          .dot { width:.5rem; height:.5rem; border-radius:50%; background:#ff7a45; box-shadow:0 0 14px #ff7a45; }
          .evidence { border-left:2px solid #ff7a45; padding:.35rem 0 .35rem .9rem; color:#aeb2bb; font-size:.86rem; }
          .footer { margin-top:3rem; padding:1.25rem 0; border-top:1px solid #282b31; color:#858a94; font-size:.82rem; }
          .footer a { color:#bfc3ca; margin-right:1rem; }
          .footer a:focus { outline:2px solid #ff8a5b; outline-offset:3px; }
          @media (max-width:760px){ .proof-grid{grid-template-columns:repeat(2,1fr);} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Agent Reliability Lab", page_icon="◆", layout="wide")
    _styles()
    is_connected = connected_mode()

    st.markdown('<div class="eyebrow">Applied AI engineering reference</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">Reliable tool-using AI,<br/>made inspectable.</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-copy">A compact Mistral reference that makes the production concerns visible: '
        'allow-listed tools, grounded policy answers, bounded retries, privacy-first telemetry, and credential-free tests.</p>',
        unsafe_allow_html=True,
    )
    label = "Connected to model provider" if is_connected else "Credential-free preview"
    st.markdown(f'<div class="mode"><span class="dot"></span>{label}</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="proof-grid">
          <div class="proof"><strong>Tool control</strong><span>Schema-bound, allow-listed execution</span></div>
          <div class="proof"><strong>Resilience</strong><span>429/5xx retry with jitter</span></div>
          <div class="proof"><strong>Observability</strong><span>OpenTelemetry metadata, no content</span></div>
          <div class="proof"><strong>Regression proof</strong><span>Secret-free CI and eval cases</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "queued_prompt" not in st.session_state:
        st.session_state.queued_prompt = None

    st.subheader("Try the execution path")
    examples = [
        "How many vacation days do employees receive?",
        "Can employees work remotely?",
        "What is the weather in Munich?",
    ]
    columns = st.columns(3)
    for column, example in zip(columns, examples):
        if column.button(example, use_container_width=True):
            st.session_state.queued_prompt = example

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("evidence"):
                st.markdown(f'<div class="evidence">{message["evidence"]}</div>', unsafe_allow_html=True)

    prompt = st.session_state.queued_prompt or st.chat_input("Ask about weather or the fictional employee policy")
    st.session_state.queued_prompt = None
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Running the request…"):
                try:
                    if is_connected:
                        response = chat_with_tools(
                            user_message=prompt,
                            tools=TOOLS,
                            tool_executor=execute_tool,
                            system_message=load_prompt("system_prompt.txt"),
                            conversation_history=_history_for_model()[:-1],
                        )
                        evidence = f"Model: {config.MISTRAL_MODEL} · Tools available: 2 · Content telemetry: off"
                    else:
                        preview = run_showcase(prompt)
                        response = preview.answer
                        tool = preview.tool or "none"
                        evidence = f"Route: {preview.route} · Tool: {tool} · {preview.latency_ms} ms · No provider call"
                    st.markdown(response)
                    st.markdown(f'<div class="evidence">{evidence}</div>', unsafe_allow_html=True)
                    trace_event("request_completed", {"input_chars": len(prompt), "connected": is_connected})
                except Exception as exc:
                    response = "The request could not be completed. Check provider configuration and local logs."
                    evidence = f"Failure type: {type(exc).__name__} · Sensitive content omitted"
                    st.error(response)
                    trace_event("request_failed", {"error_type": type(exc).__name__})
        st.session_state.messages.append({"role": "assistant", "content": response, "evidence": evidence})

    with st.expander("Architecture and trust boundaries"):
        st.markdown(
            "**Request → Mistral/Ollama → allow-listed tool → validated result → grounded answer**\n\n"
            "The model proposes tool calls; application code decides which functions can execute. "
            "Logs and spans contain latency, token counts, tool names, and error types, never prompt or response content."
        )

    with st.sidebar:
        st.header("Runtime evidence")
        st.metric("Backend", "Mistral" if config.LLM_BACKEND == "api" else "Ollama")
        st.metric("Model", config.MISTRAL_MODEL)
        st.metric("Retry attempts", config.RETRY_MAX_ATTEMPTS)
        st.caption("OpenTelemetry export: " + ("enabled" if config.OTEL_ENABLED else "disabled by default"))
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        st.divider()
        st.markdown("**Reviewer shortcuts**")
        st.markdown("[Source code](https://github.com/Andreasniss/Mistral-playground)")
        st.markdown("[CI runs](https://github.com/Andreasniss/Mistral-playground/actions)")
        st.caption("The policy is fictional and the preview is deterministic. Connected mode performs real model calls.")

    st.markdown(
        '<div class="footer"><a href="https://github.com/Andreasniss" target="_blank" rel="noopener noreferrer">Built by Andreas Nissen</a>'
        '<a href="https://github.com/Andreasniss/Mistral-playground" target="_blank" rel="noopener noreferrer">Source on GitHub</a></div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
