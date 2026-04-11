"""
demo_chat.py — interactive multi-turn chat loop

Maintains conversation history so the model can answer follow-up questions
with full context. Type 'exit' or press Ctrl+C to quit.

Note: uses get_client() directly (not llm_client.chat()) because chat()
builds a fresh messages array each call and cannot carry history.
"""
from llm_client import get_client
from prompts_loader import load_prompt
import config


def run():
    print("=== Multi-Turn Chat ===")
    print("Type your message and press Enter. Type 'exit' to quit.\n")

    client = get_client()
    messages = [{"role": "system", "content": load_prompt("system_prompt.txt")}]

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            print("Goodbye.")
            break

        messages.append({"role": "user", "content": user_input})

        if config.LLM_BACKEND == "local":
            response = client.chat.completions.create(
                model=config.MISTRAL_MODEL,
                messages=messages,
                max_tokens=config.MISTRAL_MAX_TOKENS,
                temperature=config.MISTRAL_TEMPERATURE,
            )
        else:
            response = client.chat.complete(
                model=config.MISTRAL_MODEL,
                messages=messages,
                max_tokens=config.MISTRAL_MAX_TOKENS,
                temperature=config.MISTRAL_TEMPERATURE,
            )

        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        print(f"\nAssistant: {reply}\n")


if __name__ == "__main__":
    run()
