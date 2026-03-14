from __future__ import annotations

import logging
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


def _storage_root() -> Path:
    return Path(get_settings().storage.path)


def init_storage() -> None:
    root = _storage_root()
    root.mkdir(parents=True, exist_ok=True)

    try:
        fd, tmp_path = tempfile.mkstemp(dir=root)
        os.close(fd)
        Path(tmp_path).unlink()
    except OSError as exc:
        raise RuntimeError(f"Storage path {root} is not writable: {exc}") from exc

    logger.info("Storage initialized at %s", root)


def get_audio_url(text_hash: str) -> str:
    settings = get_settings()
    base = settings.storage.public_base_url.rstrip("/")
    prefix = settings.storage.audio_prefix.strip("/")
    return f"{base}/{prefix}/{text_hash[:8]}/{text_hash}.mp3"


def write_audio(audio_bytes: bytes, text_hash: str) -> str:
    root = _storage_root()
    sub_dir = root / text_hash[:8]
    sub_dir.mkdir(parents=True, exist_ok=True)

    dest = sub_dir / f"{text_hash}.mp3"
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(audio_bytes)
    tmp.rename(dest)

    logger.info("Audio written: %s", dest)
    return get_audio_url(text_hash)


def cleanup_old_files(days: int | None = None) -> int:
    settings = get_settings()
    if days is None:
        days = settings.storage.cleanup_after_days

    root = _storage_root()
    if not root.exists():
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=days)
    deleted = 0

    for file_path in root.rglob("*.mp3"):
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                file_path.unlink()
                logger.info("Deleted old audio file: %s", file_path)
                deleted += 1
                try:
                    file_path.parent.rmdir()
                except OSError:
                    pass
        except OSError as exc:
            logger.warning("Could not process %s: %s", file_path, exc)

    logger.debug("Cleanup done: %d files deleted", deleted)
    return deleted
