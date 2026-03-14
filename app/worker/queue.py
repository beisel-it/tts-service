"""Job queue implementation using SQLite.

See Task C1 for the specification.

Atomic job claiming uses BEGIN IMMEDIATE to prevent double-pickup when
multiple worker instances run concurrently.  WAL mode must be enabled
on the database (set in the schema init).
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class QueueError(Exception):
    """General queue operation failure."""


class JobNotFoundError(QueueError):
    """No job with the given job_id exists in the database."""


# ---------------------------------------------------------------------------
# Job dict shape returned by claim_next_job / get_job_status
# ---------------------------------------------------------------------------

JobDict = dict[str, Any]


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------


class Queue:
    """SQLite-backed job queue.

    Args:
        db_path: Path to the SQLite database file.
        max_retries: How many times a job is retried before being permanently
            failed. Defaults to 3.

    Usage::

        with Queue("/data/jobs.db") as q:
            job = q.claim_next_job()
    """

    def __init__(self, db_path: str, max_retries: int = MAX_RETRIES) -> None:
        self._db_path = db_path
        self._max_retries = max_retries
        self._init_db()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "Queue":
        return self

    def __exit__(self, *_: Any) -> None:
        pass  # SQLite connections are per-operation; nothing to close here.

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def claim_next_job(self) -> JobDict | None:
        """Atomically claim the oldest pending job.

        Uses BEGIN IMMEDIATE to prevent two concurrent workers from picking
        up the same job.

        Returns:
            A dict with job fields, or *None* if the queue is empty.
        """
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT id, text, text_hash, voice_id, backend, article_id,
                       retry_count, created_at, webhook_url
                FROM   jobs
                WHERE  status = 'pending'
                ORDER  BY created_at ASC
                LIMIT  1
                """,
            ).fetchone()

            if row is None:
                conn.execute("ROLLBACK")
                logger.debug("claim_next_job: queue empty")
                return None

            job_id = row["id"]
            conn.execute(
                "UPDATE jobs SET status = 'processing' WHERE id = ?",
                (job_id,),
            )
            conn.execute("COMMIT")

        logger.debug("claim_next_job: claimed job_id=%s", job_id)
        return dict(row)

    def complete_job(
        self,
        job_id: str,
        duration_seconds: float,
        *,
        audio_url: str | None = None,
        storage_key: str | None = None,
        chars_processed: int | None = None,
        backend_used: str | None = None,
        backends_tried: list[str] | None = None,
    ) -> bool:
        """Mark a job as successfully completed.

        Args:
            job_id: The job to update.
            duration_seconds: Wall-clock seconds the synthesis took.
            audio_url: Public URL of the generated audio file (optional).
            storage_key: Internal storage path (optional).
            chars_processed: Number of characters synthesised (optional).
            backend_used: Which backend ultimately succeeded (optional).
            backends_tried: List of all backends attempted (optional, JSON).

        Returns:
            True on success.

        Raises:
            JobNotFoundError: *job_id* does not exist.
        """
        import json

        now = _utcnow()
        backends_tried_json = json.dumps(backends_tried) if backends_tried else None

        with self._connection() as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET    status           = 'done',
                       completed_at     = ?,
                       duration_seconds = ?,
                       audio_url        = COALESCE(?, audio_url),
                       storage_key      = COALESCE(?, storage_key),
                       chars_processed  = COALESCE(?, chars_processed),
                       backend          = COALESCE(?, backend),
                       backends_tried   = COALESCE(?, backends_tried),
                       error            = NULL
                WHERE  id = ?
                """,
                (
                    now,
                    duration_seconds,
                    audio_url,
                    storage_key,
                    chars_processed,
                    backend_used,
                    backends_tried_json,
                    job_id,
                ),
            )
            if cur.rowcount == 0:
                raise JobNotFoundError(f"Job '{job_id}' not found")

        logger.info(
            "complete_job: job_id=%s duration=%.2fs backend=%s",
            job_id,
            duration_seconds,
            backend_used,
        )
        return True

    def fail_job(
        self,
        job_id: str,
        error_msg: str,
        *,
        force_permanent: bool = False,
        backends_tried: list[str] | None = None,
    ) -> tuple[bool, int]:
        """Record a job failure, incrementing the retry counter.

        Args:
            job_id: The job to update.
            error_msg: Human-readable error description.
            force_permanent: If *True*, mark the job as 'failed' immediately
                regardless of retry count.
            backends_tried: List of all backends attempted (optional).

        Returns:
            ``(success, retry_count_after)`` tuple.

        Raises:
            JobNotFoundError: *job_id* does not exist.
        """
        import json

        with self._connection() as conn:
            row = conn.execute(
                "SELECT retry_count FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise JobNotFoundError(f"Job '{job_id}' not found")

            retry_count = row["retry_count"] + 1
            is_permanent = force_permanent or (retry_count >= self._max_retries)

            new_status = "failed" if is_permanent else "pending"
            now = _utcnow() if is_permanent else None
            backends_tried_json = json.dumps(backends_tried) if backends_tried else None

            conn.execute(
                """
                UPDATE jobs
                SET    retry_count    = ?,
                       status         = ?,
                       error          = ?,
                       completed_at   = COALESCE(?, completed_at),
                       backends_tried = COALESCE(?, backends_tried)
                WHERE  id = ?
                """,
                (retry_count, new_status, error_msg, now, backends_tried_json, job_id),
            )

        if is_permanent:
            logger.error(
                "fail_job: PERMANENT job_id=%s retry_count=%d error=%s",
                job_id,
                retry_count,
                error_msg,
            )
        else:
            logger.warning(
                "fail_job: transient job_id=%s retry_count=%d error=%s",
                job_id,
                retry_count,
                error_msg,
            )

        return True, retry_count

    def get_job_status(self, job_id: str) -> JobDict | None:
        """Fetch current status and metadata for a job.

        Args:
            job_id: The job to look up.

        Returns:
            Dict with status and metadata fields, or *None* if not found.
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT id, status, audio_url, error, retry_count,
                       completed_at, backend, backends_tried, duration_seconds
                FROM   jobs
                WHERE  id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create the jobs table if it does not exist yet."""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id               TEXT PRIMARY KEY,
                    article_id       TEXT,
                    text             TEXT NOT NULL,
                    text_hash        TEXT NOT NULL,
                    text_preview     TEXT,
                    status           TEXT NOT NULL DEFAULT 'pending',
                    audio_url        TEXT NOT NULL DEFAULT '',
                    storage_key      TEXT,
                    backend          TEXT,
                    voice_id         TEXT,
                    duration_seconds REAL,
                    chars_processed  INTEGER,
                    webhook_url      TEXT,
                    webhook_sent_at  TEXT,
                    error            TEXT,
                    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
                    completed_at     TEXT,
                    retry_count      INTEGER NOT NULL DEFAULT 0,
                    backends_tried   TEXT,
                    retry_backends   INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_text_hash  ON jobs(text_hash);
                CREATE INDEX IF NOT EXISTS idx_jobs_article_id ON jobs(article_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_status     ON jobs(status);
                """
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
