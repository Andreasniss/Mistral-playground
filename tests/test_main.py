from unittest.mock import patch, MagicMock
import pytest


def test_chat_sends_user_message():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test response"

    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = mock_response
        mock_get_client.return_value = mock_client

        from llm_client import chat
        result = chat("Hello")

        assert result == "Test response"
        mock_client.chat.complete.assert_called_once()
        call_args = mock_client.chat.complete.call_args
        messages = call_args.kwargs["messages"]
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Hello"


def test_chat_includes_system_message():
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Reply"

    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = mock_response
        mock_get_client.return_value = mock_client

        from llm_client import chat
        chat("Hi", system_message="You are helpful.")

        messages = mock_client.chat.complete.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."


def test_load_prompt_returns_content(tmp_path, monkeypatch):
    import prompts_loader
    monkeypatch.setattr(prompts_loader, "PROMPTS_DIR", tmp_path)
    (tmp_path / "test.txt").write_text("Hello prompt")

    result = prompts_loader.load_prompt("test.txt")
    assert result == "Hello prompt"


def test_load_prompt_raises_on_missing(tmp_path, monkeypatch):
    import prompts_loader
    monkeypatch.setattr(prompts_loader, "PROMPTS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError):
        prompts_loader.load_prompt("nonexistent.txt")
