from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_pronunciations_isolation_between_tokens(monkeypatch, tmp_path):
    # set per-test config
    cfg = tmp_path / "config.yaml"
    env = tmp_path / ".env"
    db_path = tmp_path / "jobs.db"
    audio_path = tmp_path / "audio"

    cfg.write_text(
        f"""
service_name: tts-service-test
api_base_url: http://testserver
sqlite_path: {db_path}
max_text_length: 5000
api_keys:
  - token-a
  - token-b
storage:
  public_base_url: http://testserver
  audio_prefix: audio
  path: {audio_path}
backends:
  default_backend: elevenlabs
  enabled: [elevenlabs]
  elevenlabs:
    default_voice: test
    model_id: eleven_multilingual_v2
""".strip(),
        encoding="utf-8",
    )
    env.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(cfg))

    with TestClient(app) as c:
        # create under token-a
        r = c.post(
            "/admin/pronunciations",
            headers={"X-API-Key": "token-a"},
            json={"language": "de-DE", "grapheme": "Neckargerach", "alias": "Neckargehrach"},
        )
        assert r.status_code == 201, r.text

        # token-b cannot see it
        r2 = c.get("/admin/pronunciations", headers={"X-API-Key": "token-b"})
        assert r2.status_code == 200
        assert r2.json()["items"] == []

        # token-a sees it
        r3 = c.get("/admin/pronunciations", headers={"X-API-Key": "token-a"})
        assert r3.status_code == 200
        assert len(r3.json()["items"]) == 1


def test_pronunciations_requires_auth(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    env = tmp_path / ".env"
    db_path = tmp_path / "jobs.db"
    audio_path = tmp_path / "audio"

    cfg.write_text(
        f"""
service_name: tts-service-test
api_base_url: http://testserver
sqlite_path: {db_path}
max_text_length: 5000
api_keys:
  - secret-test-key
storage:
  public_base_url: http://testserver
  audio_prefix: audio
  path: {audio_path}
backends:
  default_backend: elevenlabs
  enabled: [elevenlabs]
  elevenlabs:
    default_voice: test
    model_id: eleven_multilingual_v2
""".strip(),
        encoding="utf-8",
    )
    env.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(cfg))

    with TestClient(app) as c:
        r = c.get("/admin/pronunciations")
        assert r.status_code == 401
