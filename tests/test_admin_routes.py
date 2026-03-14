from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.backends.base import VoiceInfo
from app.config import reload_settings
from app.db.crud import create_job
from app.main import app


class _BackendStub:
    @property
    def name(self) -> str:
        return "polly"

    async def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(voice_id="v1", name="Voice 1", language="de-DE"),
            VoiceInfo(voice_id="v2", name="Voice 2", language="en-US"),
        ]


class _FailingBackendStub:
    @property
    def name(self) -> str:
        return "polly"

    async def list_voices(self) -> list[VoiceInfo]:
        raise RuntimeError("backend temporarily unavailable")


class _RouterStub:
    def __init__(self, backend) -> None:
        self._backend = backend

    def get_backend(self, backend_name=None):
        return self._backend


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
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
  azure:
    enabled: false
  polly:
    enabled: false
  piper:
    enabled: false
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


def test_health_public_and_queue_depth(admin_client):
    response = admin_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    assert payload["queue_depth"] == 0
    assert isinstance(payload["uptime_seconds"], int)


def test_health_counts_pending_and_processing(admin_client):
    from app.config import get_settings

    settings = get_settings()
    text = "hello queue"
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    job = create_job(
        settings.sqlite_path,
        text=text,
        text_hash=text_hash,
        article_id=None,
        audio_url=settings.get_audio_url(text_hash),
        backend="elevenlabs",
        voice_id="v1",
        webhook_url=None,
    )

    # set one job to processing as well
    import sqlite3

    with sqlite3.connect(settings.sqlite_path) as conn:
        conn.execute("UPDATE jobs SET status='processing' WHERE id = ?", (job["id"],))
        conn.execute(
            "INSERT INTO jobs (id, text, text_hash, status, audio_url, created_at) VALUES (?, ?, ?, 'pending', '', datetime('now'))",
            ("tts_extra", "x", "h2"),
        )

    response = admin_client.get("/health")
    assert response.status_code == 200
    assert response.json()["queue_depth"] == 2


def test_admin_voices_requires_api_key(admin_client):
    response = admin_client.get("/admin/voices")
    assert response.status_code == 401


def test_admin_voices_returns_backend_and_voices(admin_client):
    from app.api.routes_admin import get_backend_router

    app.dependency_overrides[get_backend_router] = lambda: _RouterStub(_BackendStub())
    try:
        response = admin_client.get(
            "/admin/voices", headers={"X-API-Key": "secret-test-key"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["backend"] == "polly"
    assert payload["voices"] == [
        {"id": "v1", "name": "Voice 1", "language": "de-DE"},
        {"id": "v2", "name": "Voice 2", "language": "en-US"},
    ]


def test_admin_voices_backend_error_returns_503(admin_client):
    from app.api.routes_admin import get_backend_router

    app.dependency_overrides[get_backend_router] = lambda: _RouterStub(_FailingBackendStub())
    try:
        response = admin_client.get(
            "/admin/voices", headers={"X-API-Key": "secret-test-key"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error_message"] == "backend temporarily unavailable"
