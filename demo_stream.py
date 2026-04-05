"""
demo_stream.py — streaming response demo

Shows tokens printing in real time instead of waiting for the full reply.
The model used is mistral-small-latest (faster/cheaper) to keep latency low.
"""
import sys
from llm_client import get_client
from prompts_loader import load_prompt
import config

PROMPT = "Write a short poem about the history of artificial intelligence."

def run():
    print("=== Streaming Demo ===")
    print(f"Prompt: {PROMPT}\n")
    print("Response (streaming):")
    print("-" * 40)

    client = get_client()
    with client.chat.stream(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": load_prompt("system_prompt.txt")},
            {"role": "user", "content": PROMPT},
        ],
        temperature=config.MISTRAL_TEMPERATURE,
        max_tokens=config.MISTRAL_MAX_TOKENS,
    ) as stream:
        for event in stream:
            choices = event.data.choices
            if not choices:
                continue
            delta = choices[0].delta.content
            if delta:
                print(delta, end="", flush=True)

    print("\n" + "-" * 40)


if __name__ == "__main__":
    run()
