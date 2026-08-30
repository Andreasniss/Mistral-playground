"""Deterministic, credential-free preview used by the public Streamlit demo.

The preview exercises routing, retrieval, citations, and UI observability without
pretending that a model call occurred. Connected mode remains the place to test
Mistral or a local Ollama model end to end.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

POLICY_PATH = Path(__file__).parent / "RAG" / "hr_policy.md"


@dataclass(frozen=True)
class ShowcaseResult:
    answer: str
    route: str
    tool: str | None
    evidence: tuple[str, ...]
    latency_ms: int


def _sections() -> list[tuple[str, str]]:
    title = ""
    body: list[str] = []
    sections: list[tuple[str, str]] = []
    for line in POLICY_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if title:
                sections.append((title, "\n".join(body).strip()))
            title, body = line[3:].strip(), []
        elif title:
            body.append(line)
    if title:
        sections.append((title, "\n".join(body).strip()))
    return sections


def retrieve_policy(query: str, limit: int = 2) -> list[tuple[str, str]]:
    """Return the best matching policy sections using transparent token overlap."""
    aliases = {
        "holiday": "vacation leave",
        "home": "remote work",
        "training": "professional development conference tuition",
        "parent": "parental maternity paternity",
        "benefits": "compensation insurance pension",
    }
    expanded = query.lower()
    for word, addition in aliases.items():
        if word in expanded:
            expanded += " " + addition
    terms = set(re.findall(r"[a-z0-9]+", expanded)) - {
        "a", "an", "and", "are", "do", "does", "for", "get", "how", "i",
        "in", "is", "many", "my", "of", "the", "to", "what", "work",
    }
    ranked = []
    for position, (title, body) in enumerate(_sections()):
        haystack = set(re.findall(r"[a-z0-9]+", f"{title} {body}".lower()))
        score = len(terms & haystack)
        ranked.append((score, -position, title, body))
    return [(title, body) for score, _, title, body in sorted(ranked, reverse=True)[:limit] if score]


def classify_request(prompt: str) -> str:
    text = prompt.lower()
    if any(word in text for word in ("vacation", "holiday", "leave", "remote", "policy", "benefit", "training")):
        return "policy_retrieval"
    if any(word in text for word in ("weather", "temperature", "jacket", "rain")):
        return "weather_tool"
    return "direct_answer"


def run_showcase(prompt: str) -> ShowcaseResult:
    """Return an honest offline preview result with visible execution evidence."""
    started = time.perf_counter()
    route = classify_request(prompt)

    if route == "policy_retrieval":
        matches = retrieve_policy(prompt)
        if matches:
            title, body = matches[0]
            bullets = [line[2:] for line in body.splitlines() if line.startswith("- ")][:3]
            answer = "Here is the relevant policy summary:\n\n" + "\n".join(f"- {item}" for item in bullets)
            answer += f"\n\n**Source:** [{title}]"
            evidence = (title,)
        else:
            answer = "I could not find a supported answer in the local policy document."
            evidence = ()
        tool = "search_policy"
    elif route == "weather_tool":
        answer = (
            "In connected mode, Mistral selects the weather function, the application validates "
            "its arguments, and Open-Meteo supplies the current observation. This offline preview "
            "does not fabricate live weather data."
        )
        tool = "get_current_weather"
        evidence = ("Live data intentionally disabled in preview",)
    else:
        answer = (
            "This credential-free preview is designed to demonstrate routing and grounded answers. "
            "Choose a policy or weather example, or connect Mistral/Ollama for unrestricted chat."
        )
        tool = None
        evidence = ("No provider call",)

    latency_ms = max(1, round((time.perf_counter() - started) * 1000))
    return ShowcaseResult(answer, route, tool, evidence, latency_ms)
