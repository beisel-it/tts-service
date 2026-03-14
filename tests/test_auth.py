from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import app


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    db_path = tmp_path / "jobs.db"
    audio_path = tmp_path / "audio"
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    config_path.write_text(
        f"""
service_name: tts-service-test
api_base_url: http://testserver
sqlite_path: {db_path}
api_key: secret-test-key
storage:
  public_base_url: https://audio.example.com
  audio_prefix: audio
  path: {audio_path}
backends:
  default_backend: elevenlabs
  enabled:
    - elevenlabs
  elevenlabs:
    default_voice: test-voice
    model_id: eleven_multilingual_v2
        """.strip(),
        encoding="utf-8",
    )
    env_path.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(config_path))
    monkeypatch.delenv("TTS_STORAGE__PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("TTS_STORAGE__PATH", raising=False)
    monkeypatch.delenv("TTS_SQLITE_PATH", raising=False)
    monkeypatch.delenv("TTS_API_KEY", raising=False)

    reload_settings()
    with TestClient(app) as client:
        yield client


def test_health_requires_no_auth(auth_client):
    response = auth_client.get("/health")
    assert response.status_code == 200


def test_synthesize_without_key_returns_401(auth_client):
    response = auth_client.post("/synthesize", json={"text": "Hallo"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key"


def test_synthesize_with_wrong_key_returns_401(auth_client):
    response = auth_client.post(
        "/synthesize",
        json={"text": "Hallo"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_synthesize_with_correct_key_proceeds(auth_client):
    response = auth_client.post(
        "/synthesize",
        json={"text": "Hallo Welt"},
        headers={"X-API-Key": "secret-test-key"},
    )
    # Either 201 (new job) or 200 (cached) — not 401
    assert response.status_code in (200, 201)


def test_dev_mode_no_key_configured(tmp_path, monkeypatch):
    """When no api_key is set, all requests should pass through."""
    db_path = tmp_path / "jobs.db"
    audio_path = tmp_path / "audio"
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    config_path.write_text(
        f"""
service_name: tts-service-test
api_base_url: http://testserver
sqlite_path: {db_path}
storage:
  public_base_url: https://audio.example.com
  audio_prefix: audio
  path: {audio_path}
backends:
  default_backend: elevenlabs
  enabled:
    - elevenlabs
  elevenlabs:
    default_voice: test-voice
    model_id: eleven_multilingual_v2
        """.strip(),
        encoding="utf-8",
    )
    env_path.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(config_path))
    monkeypatch.delenv("TTS_STORAGE__PATH", raising=False)
    monkeypatch.delenv("TTS_SQLITE_PATH", raising=False)
    monkeypatch.delenv("TTS_API_KEY", raising=False)

    reload_settings()
    with TestClient(app) as client:
        response = client.post("/synthesize", json={"text": "Hallo"})
        assert response.status_code in (200, 201)
