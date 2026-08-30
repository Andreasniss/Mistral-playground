from unittest.mock import MagicMock, patch

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


def test_chat_includes_conversation_history_before_new_turn():
    history = [
        {"role": "user", "content": "My city is Munich."},
        {"role": "assistant", "content": "Understood."},
    ]
    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_response("Munich")
        mock_get_client.return_value = mock_client

        from llm_client import chat
        chat("Which city did I mention?", conversation_history=history)

        messages = mock_client.chat.complete.call_args.kwargs["messages"]
        assert messages == history + [{"role": "user", "content": "Which city did I mention?"}]


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


def test_missing_cloud_key_fails_only_when_client_is_requested(monkeypatch):
    import config
    import llm_client

    monkeypatch.setattr(config, "LLM_BACKEND", "api")
    monkeypatch.setattr(config, "MISTRAL_API_KEY", None)
    monkeypatch.setattr(llm_client, "_client", None)

    with pytest.raises(EnvironmentError, match="MISTRAL_API_KEY is not set"):
        llm_client.get_client()


def test_modules_import_without_cloud_key():
    import os
    import subprocess
    import sys

    clean_env = os.environ.copy()
    clean_env.pop("MISTRAL_API_KEY", None)
    clean_env["LLM_BACKEND"] = "api"
    clean_env["OTEL_ENABLED"] = "false"

    result = subprocess.run(
        [sys.executable, "-c", "import config; import llm_client"],
        env=clean_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_disabled_telemetry_does_not_create_exporter(monkeypatch):
    import config
    import llm_client

    monkeypatch.setattr(config, "OTEL_ENABLED", False)
    with patch("llm_client.OTLPSpanExporter") as mock_exporter:
        assert llm_client._configure_tracing() is False
    mock_exporter.assert_not_called()


def test_chat_logs_exclude_prompt_and_response_content(caplog):
    import logging

    secret_prompt = "PROMPT_SECRET_7e91"
    secret_response = "RESPONSE_SECRET_3a42"
    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = _make_response(secret_response)
        mock_get_client.return_value = mock_client

        from llm_client import chat
        with caplog.at_level(logging.DEBUG, logger="llm_client"):
            assert chat(secret_prompt) == secret_response

    captured = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_prompt not in captured
    assert secret_response not in captured


def test_chat_span_encloses_provider_call():
    events = []

    class FakeSpan:
        def __enter__(self):
            events.append("span_enter")
            return self

        def __exit__(self, exc_type, exc, traceback):
            events.append("span_exit")

        def set_attribute(self, key, value):
            pass

    class FakeTracer:
        def start_as_current_span(self, name, **kwargs):
            return FakeSpan()

    with patch("llm_client.trace.get_tracer", return_value=FakeTracer()), \
         patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()

        def provider_call(**kwargs):
            events.append("provider_call")
            return _make_response("OK")

        mock_client.chat.complete.side_effect = provider_call
        mock_get_client.return_value = mock_client

        from llm_client import chat
        assert chat("Hello") == "OK"

    assert events == ["span_enter", "provider_call", "span_exit"]


def test_tool_logs_exclude_argument_and_result_values(caplog):
    import logging

    secret_prompt = "TOOL_PROMPT_SECRET_4b11"
    secret_argument = "TOOL_ARGUMENT_SECRET_f125"
    secret_result = "TOOL_RESULT_SECRET_8d30"

    tool_call = MagicMock()
    tool_call.id = "call-1"
    tool_call.function.name = "lookup"
    tool_call.function.arguments = '{"query": "' + secret_argument + '"}'

    first_response = _make_response("")
    first_response.choices[0].finish_reason = "tool_calls"
    first_response.choices[0].message.tool_calls = [tool_call]
    second_response = _make_response("done")
    second_response.choices[0].finish_reason = "stop"

    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = [first_response, second_response]
        mock_get_client.return_value = mock_client

        from llm_client import chat_with_tools
        with caplog.at_level(logging.DEBUG, logger="llm_client"):
            result = chat_with_tools(
                secret_prompt,
                tools=[{"type": "function", "function": {"name": "lookup"}}],
                tool_executor=lambda name, args: secret_result,
            )

    assert result == "done"
    captured = "\n".join(record.getMessage() for record in caplog.records)
    assert secret_prompt not in captured
    assert secret_argument not in captured
    assert secret_result not in captured


def test_tool_loop_is_bounded(monkeypatch):
    tool_call = MagicMock()
    tool_call.id = "call-1"
    tool_call.function.name = "lookup"
    tool_call.function.arguments = '{"query": "safe"}'

    looping_response = _make_response("")
    looping_response.choices[0].finish_reason = "tool_calls"
    looping_response.choices[0].message.tool_calls = [tool_call]

    import config
    monkeypatch.setattr(config, "MAX_TOOL_ROUNDS", 1)
    with patch("llm_client.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.complete.return_value = looping_response
        mock_get_client.return_value = mock_client

        from llm_client import chat_with_tools
        with pytest.raises(RuntimeError, match="Tool-call limit exceeded"):
            chat_with_tools(
                "Loop forever",
                tools=[{"type": "function", "function": {"name": "lookup"}}],
                tool_executor=lambda name, args: "result",
            )


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
