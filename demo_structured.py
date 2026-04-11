"""demo_structured.py — structured JSON output using response_format.

Uses Mistral's JSON mode to extract structured data from unstructured text.
The model is instructed to respond with JSON; output is validated with Pydantic.

Note: uses get_client() directly (not llm_client.chat()) because response_format
is not yet a parameter on chat(). This is intentional for a demo script.

Run:
    python3 demo_structured.py
"""

import json

from pydantic import BaseModel, ValidationError

from config import MISTRAL_MODEL
from llm_client import get_client
from logger import get_logger

log = get_logger(__name__)


class MovieReview(BaseModel):
    title: str
    sentiment: str   # "positive", "negative", or "mixed"
    score: float     # 0.0 – 10.0
    summary: str     # one-sentence verdict


SYSTEM_PROMPT = (
    "You are a film critic assistant. Analyse the review and respond with a JSON object "
    "matching exactly this schema: "
    '{"title": string, "sentiment": "positive"|"negative"|"mixed", '
    '"score": float 0-10, "summary": string one sentence}. '
    "Respond with JSON only — no markdown, no extra text."
)

REVIEW = """
Dune: Part Two is a visual masterpiece. Villeneuve takes everything that worked
in Part One and amplifies it — the scale, the sound design, the performances.
Zendaya finally gets the screen time she deserved and delivers. My only gripe:
the third act rushes what the book takes its time with. Still, easily one of
the best sci-fi films of the decade.
"""


def run_structured_demo() -> None:
    client = get_client()
    log.info("Sending review for structured extraction (model=%s)", MISTRAL_MODEL)

    response = client.chat.complete(
        model=MISTRAL_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": REVIEW.strip()},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = response.choices[0].message.content
    log.debug("Raw response: %s", raw)

    try:
        review = MovieReview(**json.loads(raw))
        print(f"\nTitle:     {review.title}")
        print(f"Sentiment: {review.sentiment}")
        print(f"Score:     {review.score}/10")
        print(f"Summary:   {review.summary}\n")
    except (ValidationError, json.JSONDecodeError) as exc:
        log.error("Failed to parse structured response: %s\nRaw: %s", exc, raw)


if __name__ == "__main__":
    run_structured_demo()
