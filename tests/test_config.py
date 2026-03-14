from __future__ import annotations

from pathlib import Path

from app.config import get_settings, reload_settings


def test_settings_load_from_yaml_and_env(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    config_path.write_text(
        """
service_name: yaml-service
api_base_url: http://yaml.local
sqlite_path: /tmp/yaml.db
storage:
  public_base_url: https://yaml.example.com
  audio_prefix: media
queue:
  default_fetch_limit: 3
webhook:
  enabled: true
  timeout_seconds: 10
backends:
  default_backend: elevenlabs
  enabled:
    - elevenlabs
  elevenlabs:
    default_voice: yaml-voice
    model_id: eleven_multilingual_v2
        """.strip(),
        encoding="utf-8",
    )
    env_path.write_text(
        "TTS_STORAGE__PUBLIC_BASE_URL=https://env.example.com\nTTS_SQLITE_PATH=/tmp/env.db\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(config_path))

    reload_settings()
    settings = get_settings()

    assert settings.service_name == "yaml-service"
    assert settings.queue.default_fetch_limit == 3
    assert settings.storage.public_base_url == "https://env.example.com"
    assert settings.sqlite_path == "/tmp/env.db"
