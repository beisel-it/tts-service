from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import app


@pytest.fixture
def configured_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "jobs.db"
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    audio_path = tmp_path / "audio"

    config_path.write_text(
        """
service_name: tts-service-test
api_base_url: http://testserver
sqlite_path: __DB_PATH__
max_text_length: 5000
storage:
  public_base_url: https://audio.example.com
  audio_prefix: audio
  path: __AUDIO_PATH__
  cleanup_after_days: 7
queue:
  default_fetch_limit: 5
webhook:
  enabled: true
  timeout_seconds: 15
backends:
  default_backend: elevenlabs
  enabled:
    - elevenlabs
  elevenlabs:
    default_voice: test-voice
    model_id: eleven_multilingual_v2
        """
        .strip()
        .replace("__DB_PATH__", str(db_path))
        .replace("__AUDIO_PATH__", str(audio_path)),
        encoding="utf-8",
    )

    env_path.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(config_path))
    monkeypatch.delenv("TTS_STORAGE__PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("TTS_STORAGE__PATH", raising=False)
    monkeypatch.delenv("TTS_SQLITE_PATH", raising=False)

    reload_settings()

    return {
        "db_path": db_path,
        "audio_path": audio_path,
        "config_path": config_path,
        "env_path": env_path,
    }


@pytest.fixture
def client(configured_env):
    with TestClient(app) as test_client:
        yield test_client
