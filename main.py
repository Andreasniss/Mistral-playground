from llm_client import chat
from prompts_loader import load_prompt


def run_basic_chat():
    system = load_prompt("system_prompt.txt")
    user_input = "Explain what Mistral AI is in two sentences."

    print("=== Basic Chat ===")
    print(f"User: {user_input}")
    response = chat(user_input, system_message=system)
    print(f"Assistant: {response}\n")


def run_summarize(text: str):
    template = load_prompt("summarize.txt")
    prompt = template.replace("{{TEXT}}", text)

    print("=== Summarize ===")
    response = chat(prompt)
    print(f"Summary: {response}\n")


if __name__ == "__main__":
    run_basic_chat()

    sample_text = (
        "Mistral AI is a French company founded in 2023 that develops open and proprietary "
        "large language models. Their models are known for efficiency and strong performance "
        "relative to their size. They offer both open-weight models like Mistral 7B and "
        "commercial APIs with models like Mistral Large."
    )
    run_summarize(sample_text)
