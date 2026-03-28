from unittest.mock import patch, MagicMock
import pytest


def _make_response(content="Test response", prompt_tokens=10, completion_tokens=20):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    mock_response.usage.total_tokens = prompt_tokens + completion_tokens
    return mock_response


def test_chat_sends_user_message():
    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_response("Test response")
        mock_get_client.return_value = mock_client

        from llm_client import chat
        result = chat("Hello")

        assert result == "Test response"
        mock_client.chat.complete.assert_called_once()
        messages = mock_client.chat.complete.call_args.kwargs["messages"]
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Hello"


def test_chat_includes_system_message():
    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_response("Reply")
        mock_get_client.return_value = mock_client

        from llm_client import chat
        chat("Hi", system_message="You are helpful.")

        messages = mock_client.chat.complete.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are helpful."


def test_chat_logs_request_and_response(caplog):
    import logging
    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_response("Hi", prompt_tokens=5, completion_tokens=3)
        mock_get_client.return_value = mock_client

        from llm_client import chat
        with caplog.at_level(logging.INFO, logger="llm_client"):
            chat("Hello")

        messages = [r.message for r in caplog.records]
        assert any("Request" in m for m in messages)
        assert any("Response" in m for m in messages)
        assert any("latency" in m for m in messages)
        assert any("total_tokens" in m for m in messages)


def test_chat_logs_error_on_failure(caplog):
    import logging
    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = RuntimeError("API down")
        mock_get_client.return_value = mock_client

        from llm_client import chat
        with caplog.at_level(logging.ERROR, logger="llm_client"):
            with pytest.raises(RuntimeError):
                chat("Hello")

        assert any("failed" in r.message for r in caplog.records)


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
