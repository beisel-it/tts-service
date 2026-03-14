"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Config, reset_config
from app.storage import local as local_storage


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Ensure the config singleton is cleared between tests."""
    reset_config()
    local_storage._storage.cache_clear()
    yield
    reset_config()
    local_storage._storage.cache_clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient wired to a temporary SQLite database."""
    from app.main import app

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
    monkeypatch.delenv("TTS_STORAGE__PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("TTS_STORAGE__PATH", raising=False)
    monkeypatch.delenv("TTS_SQLITE_PATH", raising=False)
    monkeypatch.delenv("TTS_API_KEY", raising=False)

    reset_config()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def configured_env(tmp_path, monkeypatch):
    """Temporary config+env setup for DB/storage-oriented tests."""
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

    reset_config()
    local_storage._storage.cache_clear()
    return {"db_path": db_path, "audio_path": audio_path, "config_path": config_path}
