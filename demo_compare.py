"""
demo_compare.py — side-by-side model comparison

Runs the same prompt through mistral-small-latest and mistral-large-latest,
then prints both responses with token usage so you can compare quality vs cost.
"""
import time
from llm_client import get_client
from prompts_loader import load_prompt
import config

MODELS = [
    "mistral-small-latest",
    "mistral-large-latest",
]

PROMPT = (
    "Explain the difference between supervised and unsupervised learning "
    "in two sentences, using a concrete real-world example for each."
)


def run():
    print("=== Model Comparison ===")
    print(f"Prompt: {PROMPT}\n")
    print("=" * 60)

    client = get_client()
    system = load_prompt("system_prompt.txt")
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": PROMPT},
    ]

    results = []
    for model in MODELS:
        start = time.perf_counter()
        response = client.chat.complete(
            model=model,
            messages=messages,
            temperature=config.MISTRAL_TEMPERATURE,
            max_tokens=config.MISTRAL_MAX_TOKENS,
        )
        elapsed = time.perf_counter() - start
        results.append((model, response, elapsed))

    for model, response, elapsed in results:
        usage = response.usage
        content = response.choices[0].message.content
        print(f"\nModel: {model}")
        print(f"Latency: {elapsed:.2f}s  |  Tokens: {usage.prompt_tokens} prompt + {usage.completion_tokens} completion = {usage.total_tokens} total")
        print("-" * 60)
        print(content)
        print("=" * 60)


if __name__ == "__main__":
    run()
