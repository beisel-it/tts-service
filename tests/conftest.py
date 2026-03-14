"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import reset_config, reload_settings
from app.db.schema import init_db
from app.main import app


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Ensure the config singleton is cleared between tests."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def configured_env(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobs.db"
    audio_path = tmp_path / "audio"
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    config_path.write_text(
        f"""
service_name: tts-service-test
api_base_url: http://testserver
sqlite_path: {db_path}
max_text_length: 5000
storage:
  public_base_url: https://audio.example.com
  audio_prefix: audio
  path: {audio_path}
  cleanup_after_days: 7
queue:
  default_fetch_limit: 10
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
    monkeypatch.delenv("TTS_API_KEY", raising=False)
    monkeypatch.delenv("TTS_SQLITE_PATH", raising=False)
    monkeypatch.delenv("TTS_STORAGE__PATH", raising=False)
    monkeypatch.delenv("TTS_STORAGE__PUBLIC_BASE_URL", raising=False)

    settings = reload_settings()
    init_db(settings.sqlite_path)
    return {"db_path": db_path, "audio_path": audio_path, "config_path": config_path}


@pytest.fixture
def client(configured_env):
    with TestClient(app) as test_client:
        yield test_client
