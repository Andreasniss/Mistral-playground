"""
demo_chat.py — interactive multi-turn chat loop

Maintains conversation history so the model can answer follow-up questions
with full context. Type 'exit' or press Ctrl+C to quit.
"""
from llm_client import chat, get_client
from prompts_loader import load_prompt
import config


def run():
    print("=== Multi-Turn Chat ===")
    print("Type your message and press Enter. Type 'exit' to quit.\n")

    system_message = load_prompt("system_prompt.txt")

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

        reply = chat(user_input, system_message=system_message)
        print(f"\nAssistant: {reply}\n")


if __name__ == "__main__":
    run()
