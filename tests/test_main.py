from unittest.mock import patch, MagicMock, call
import pytest


def _make_response(content="Test response", prompt_tokens=10, completion_tokens=20):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_response.usage.prompt_tokens = prompt_tokens
    mock_response.usage.completion_tokens = completion_tokens
    mock_response.usage.total_tokens = prompt_tokens + completion_tokens
    return mock_response


def _retryable_exc(status_code=429):
    exc = Exception(f"HTTP {status_code}")
    exc.status_code = status_code
    return exc


# --- chat() core behaviour ---

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


# --- retry logic ---

def test_retry_succeeds_after_transient_429():
    with patch("llm_client.get_client") as mock_get_client, \
         patch("llm_client.time.sleep"):
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = [
            _retryable_exc(429),
            _make_response("OK"),
        ]
        mock_get_client.return_value = mock_client

        from llm_client import chat
        result = chat("Hello")

        assert result == "OK"
        assert mock_client.chat.complete.call_count == 2


def test_retry_exhausted_raises_last_exception():
    with patch("llm_client.get_client") as mock_get_client, \
         patch("llm_client.time.sleep"):
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = _retryable_exc(503)
        mock_get_client.return_value = mock_client

        import config
        from llm_client import chat
        with pytest.raises(Exception, match="503"):
            chat("Hello")

        assert mock_client.chat.complete.call_count == config.RETRY_MAX_ATTEMPTS


def test_non_retryable_error_raises_immediately():
    with patch("llm_client.get_client") as mock_get_client, \
         patch("llm_client.time.sleep") as mock_sleep:
        mock_client = MagicMock()
        exc = Exception("Bad request")
        exc.status_code = 400
        mock_client.chat.complete.side_effect = exc
        mock_get_client.return_value = mock_client

        from llm_client import chat
        with pytest.raises(Exception, match="Bad request"):
            chat("Hello")

        # no sleep — should have failed immediately without retrying
        mock_sleep.assert_not_called()
        assert mock_client.chat.complete.call_count == 1


def test_retry_respects_retry_after_header():
    # The Mistral API sets a Retry-After header on 429 responses.
    # Our code should use that value instead of calculating its own delay.
    with patch("llm_client.get_client") as mock_get_client, \
         patch("llm_client.time.sleep") as mock_sleep:
        exc = _retryable_exc(429)
        exc.headers = {"Retry-After": "7"}
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = [exc, _make_response("OK")]
        mock_get_client.return_value = mock_client

        from llm_client import chat
        chat("Hello")

        # sleep must have been called with exactly the Retry-After value
        mock_sleep.assert_called_once_with(7.0)


def test_retry_uses_exponential_backoff():
    with patch("llm_client.get_client") as mock_get_client, \
         patch("llm_client.time.sleep") as mock_sleep, \
         patch("llm_client.random.uniform", return_value=0.0):
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = [
            _retryable_exc(429),
            _retryable_exc(429),
            _make_response("OK"),
        ]
        mock_get_client.return_value = mock_client

        import config
        from llm_client import chat
        chat("Hello")

        delays = [c.args[0] for c in mock_sleep.call_args_list]
        # each delay should be larger than the previous (exponential)
        assert delays[1] > delays[0]
        # delays must not exceed max
        assert all(d <= config.RETRY_MAX_DELAY for d in delays)


# --- logging ---

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


def test_chat_logs_warning_on_retry(caplog):
    import logging
    with patch("llm_client.get_client") as mock_get_client, \
         patch("llm_client.time.sleep"):
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = [
            _retryable_exc(429),
            _make_response("OK"),
        ]
        mock_get_client.return_value = mock_client

        from llm_client import chat
        with caplog.at_level(logging.WARNING, logger="llm_client"):
            chat("Hello")

        assert any("Retryable" in r.message for r in caplog.records)


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


# --- prompts ---

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
