"""Local filesystem audio storage.

See ARCHITECTURE.md §6 and Task A3 for the specification.

Directory layout: {storage_path}/{hash[:8]}/{hash}.mp3
Public URL:       {public_base_url}/{hash[:8]}/{hash}.mp3
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from app.config import StorageConfig, get_settings

logger = logging.getLogger(__name__)


class LocalStorage:
    """Manages audio files on the local filesystem.

    Args:
        config: Storage configuration section.
    """

    def __init__(self, config: StorageConfig) -> None:
        self._base = Path(config.path)
        self._public_base = config.public_base_url.rstrip("/")
        self._audio_prefix = config.audio_prefix.strip("/")
        self._cleanup_days = config.cleanup_after_days

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def init_storage(self) -> None:
        """Create the storage directory and verify write permissions.

        Raises:
            OSError: If the directory cannot be created or written to.
        """
        self._base.mkdir(parents=True, exist_ok=True)
        # Verify write permission via temp file
        with tempfile.NamedTemporaryFile(dir=self._base, delete=True):
            pass
        logger.info("Storage initialised at %s", self._base)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_audio(self, audio_bytes: bytes, text_hash: str) -> str:
        """Write audio bytes to the storage path and return the public URL.

        The write is atomic: bytes are first written to a temp file, then
        renamed to the final destination (POSIX rename is atomic).

        Args:
            audio_bytes: Raw audio data (e.g. MP3 bytes).
            text_hash: SHA-256 hex digest of the source text.

        Returns:
            Public URL for the written file.
        """
        dest = self._audio_path(text_hash)
        dest.parent.mkdir(parents=True, exist_ok=True)

        tmp_fd, tmp_path = tempfile.mkstemp(dir=dest.parent, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(audio_bytes)
            os.replace(tmp_path, dest)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        url = self.get_audio_url(text_hash)
        logger.info("Audio written: %s (%d bytes) → %s", dest, len(audio_bytes), url)
        return url

    # ------------------------------------------------------------------
    # URL generation
    # ------------------------------------------------------------------

    def get_audio_url(self, text_hash: str) -> str:
        """Return the public URL for a given text hash (no I/O).

        The URL is deterministic and can be computed before the file exists,
        enabling the promise-URL model (ARCHITECTURE.md §1).
        """
        return f"{self._public_base}/{self._audio_prefix}/{text_hash[:8]}/{text_hash}.mp3"

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_old_files(self, days: int | None = None) -> int:
        """Delete audio files older than *days* days.

        Args:
            days: Age threshold in days. Defaults to ``config.cleanup_after_days``.

        Returns:
            Number of files deleted.
        """
        threshold_days = days if days is not None else self._cleanup_days
        cutoff = datetime.now() - timedelta(days=threshold_days)
        deleted = 0

        for mp3 in self._base.rglob("*.mp3"):
            try:
                mtime = datetime.fromtimestamp(mp3.stat().st_mtime)
                if mtime < cutoff:
                    mp3.unlink()
                    logger.debug("Cleanup: deleted %s (mtime %s)", mp3, mtime)
                    deleted += 1
                    # Remove parent dir if now empty
                    try:
                        mp3.parent.rmdir()
                    except OSError:
                        pass
            except OSError as exc:
                logger.warning("Cleanup: could not process %s: %s", mp3, exc)

        logger.info("Cleanup complete: deleted %d files (threshold %d days)", deleted, threshold_days)
        return deleted

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audio_path(self, text_hash: str) -> Path:
        return self._base / text_hash[:8] / f"{text_hash}.mp3"


@lru_cache(maxsize=1)
def _storage() -> LocalStorage:
    settings = get_settings()
    return LocalStorage(settings.storage)


def init_storage() -> None:
    """Initialize local audio storage from global settings."""
    try:
        _storage().init_storage()
    except OSError as exc:
        raise RuntimeError(f"storage path is not writable: {exc}") from exc


def write_audio(audio_bytes: bytes, text_hash: str) -> str:
    """Write audio bytes and return public URL."""
    return _storage().write_audio(audio_bytes, text_hash)


def get_audio_url(text_hash: str) -> str:
    """Return deterministic public URL for text hash."""
    return _storage().get_audio_url(text_hash)


def cleanup_old_files(days: int | None = None) -> int:
    """Delete stale audio files and return deletion count."""
    return _storage().cleanup_old_files(days=days)
