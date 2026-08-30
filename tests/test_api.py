from fastapi.testclient import TestClient

import api
import config

client = TestClient(api.app)


def test_health_is_public_and_contains_no_secret(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "server-secret")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model": config.MISTRAL_MODEL}
    assert "server-secret" not in response.text


def test_chat_rejects_missing_or_invalid_api_key(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "server-secret")
    assert client.post("/chat", json={"message": "hello"}).status_code == 401
    response = client.post(
        "/chat",
        headers={"X-API-Key": "wrong"},
        json={"message": "hello"},
    )
    assert response.status_code == 401
