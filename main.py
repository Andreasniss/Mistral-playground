from llm_client import chat
from prompts_loader import load_prompt


def run_basic_chat():
    system = load_prompt("system_prompt.txt")
    user_input = "Explain what Mistral AI is in two sentences."

    print("=== Basic Chat ===")
    print(f"User: {user_input}")
    response = chat(user_input, system_message=system)
    print(f"Assistant: {response}\n")


def run_summarize():
    prompt = load_prompt("summarize.txt")

    print("=== Summarize ===")
    response = chat(prompt)
    print(f"Summary: {response}\n")


if __name__ == "__main__":
    run_basic_chat()

    run_summarize()
