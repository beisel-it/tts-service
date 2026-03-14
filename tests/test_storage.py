from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.config import reload_settings
from app.storage.local import cleanup_old_files, get_audio_url, init_storage, write_audio


@pytest.fixture
def storage_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    audio_path = tmp_path / "audio"
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    config_path.write_text(
        f"""
storage:
  public_base_url: https://audio.example.com
  audio_prefix: audio
  path: {audio_path}
  cleanup_after_days: 7
        """.strip(),
        encoding="utf-8",
    )
    env_path.write_text("", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(config_path))
    monkeypatch.delenv("TTS_STORAGE__PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("TTS_STORAGE__PATH", raising=False)

    reload_settings()
    return {"audio_path": audio_path}


def test_init_storage_creates_directory(storage_env):
    audio_path = storage_env["audio_path"]
    assert not audio_path.exists()
    init_storage()
    assert audio_path.is_dir()


def test_init_storage_fails_on_unwritable_path(tmp_path: Path, monkeypatch):
    bad_path = tmp_path / "no_access"
    bad_path.mkdir()
    bad_path.chmod(0o444)

    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    config_path.write_text(
        f"storage:\n  path: {bad_path}\n  public_base_url: http://x\n  audio_prefix: audio",
        encoding="utf-8",
    )
    env_path.write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_CONFIG_FILE", str(config_path))
    monkeypatch.delenv("TTS_STORAGE__PATH", raising=False)
    reload_settings()

    with pytest.raises(RuntimeError, match="not writable"):
        init_storage()

    bad_path.chmod(0o755)  # restore for cleanup


def test_write_audio_creates_subdirectory(storage_env):
    init_storage()
    text_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    write_audio(b"fake-audio", text_hash)
    sub_dir = storage_env["audio_path"] / text_hash[:8]
    assert sub_dir.is_dir()
    assert (sub_dir / f"{text_hash}.mp3").exists()


def test_write_audio_returns_correct_url(storage_env):
    init_storage()
    text_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    url = write_audio(b"fake-audio", text_hash)
    assert url == f"https://audio.example.com/audio/{text_hash[:8]}/{text_hash}.mp3"


def test_get_audio_url_matches_written_file(storage_env):
    init_storage()
    text_hash = "bbbbbbbbccccccccddddddddeeeeeeeeffffffffaaaaaaaa1111111122222222"
    write_audio(b"data", text_hash)
    assert get_audio_url(text_hash) == write_audio(b"data", text_hash)


def test_write_audio_overwrites_same_hash(storage_env):
    init_storage()
    text_hash = "ccccccccddddddddeeeeeeeeffffffff00000000111111112222222233333333"
    write_audio(b"first", text_hash)
    write_audio(b"second", text_hash)  # must not raise
    dest = storage_env["audio_path"] / text_hash[:8] / f"{text_hash}.mp3"
    assert dest.read_bytes() == b"second"


def test_cleanup_old_files_removes_old_files(storage_env):
    init_storage()
    text_hash = "ddddddddeeeeeeeeffffffff0000000011111111222222223333333344444444"
    write_audio(b"old-data", text_hash)
    dest = storage_env["audio_path"] / text_hash[:8] / f"{text_hash}.mp3"
    # Set mtime to 10 days ago
    old_mtime = time.time() - 10 * 86400
    import os
    os.utime(dest, (old_mtime, old_mtime))

    deleted = cleanup_old_files(days=7)
    assert deleted == 1
    assert not dest.exists()


def test_cleanup_respects_recent_files(storage_env):
    init_storage()
    text_hash = "eeeeeeeeffffffff000000001111111122222222333333334444444455555555"
    write_audio(b"new-data", text_hash)
    deleted = cleanup_old_files(days=7)
    assert deleted == 0
    dest = storage_env["audio_path"] / text_hash[:8] / f"{text_hash}.mp3"
    assert dest.exists()
