"""
demo_chat.py — interactive multi-turn chat loop

Maintains conversation history so the model can answer follow-up questions
with full context. Type 'exit' or press Ctrl+C to quit.
"""
from llm_client import get_client
from prompts_loader import load_prompt
import config


def run():
    print("=== Multi-Turn Chat ===")
    print("Type your message and press Enter. Type 'exit' to quit.\n")

    system_message = load_prompt("system_prompt.txt")
    history = []
    client = get_client()

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

        history.append({"role": "user", "content": user_input})

        messages = [{"role": "system", "content": system_message}] + history

        response = client.chat.complete(
            model=config.MISTRAL_MODEL,
            messages=messages,
            temperature=config.MISTRAL_TEMPERATURE,
            max_tokens=config.MISTRAL_MAX_TOKENS,
        )

        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})

        print(f"\nAssistant: {reply}\n")


if __name__ == "__main__":
    run()
