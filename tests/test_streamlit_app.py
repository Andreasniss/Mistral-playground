from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_reviewer_preview_renders_and_completes_grounded_prompt():
    app_path = Path(__file__).parents[1] / "demo_streamlit.py"
    app = AppTest.from_file(app_path, default_timeout=15).run()
    assert not app.exception
    assert any("Credential-free preview" in item.value for item in app.markdown)

    app.button[0].click().run()

    assert not app.exception
    assert len(app.chat_message) == 2
    answer = app.chat_message[1].markdown[0].value
    evidence = app.chat_message[1].markdown[1].value
    assert "25 paid vacation days" in answer
    assert "Vacation and Leave Policy" in answer
    assert "No provider call" in evidence
