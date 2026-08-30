from showcase import classify_request, retrieve_policy, run_showcase


def test_policy_retrieval_returns_grounded_section():
    result = retrieve_policy("How many vacation days do I get?")
    assert result[0][0] == "Vacation and Leave Policy"
    assert "25 paid vacation days" in result[0][1]


def test_preview_never_fabricates_live_weather():
    result = run_showcase("What is the weather in Munich?")
    assert result.route == "weather_tool"
    assert result.tool == "get_current_weather"
    assert "does not fabricate" in result.answer


def test_unsupported_request_is_explicitly_limited():
    assert classify_request("Write a poem") == "direct_answer"
    assert "preview" in run_showcase("Write a poem").answer
