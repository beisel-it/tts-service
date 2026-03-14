from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _connect(sqlite_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def create_job(
    sqlite_path: str,
    *,
    text: str,
    text_hash: str,
    article_id: str | None,
    audio_url: str,
    backend: str,
    voice_id: str | None,
    webhook_url: str | None,
) -> dict:
    job_id = f"tts_{uuid4().hex[:8]}"
    created_at = _utc_now()
    text_preview = text[:100]

    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, article_id, text, text_hash, text_preview, status, audio_url,
                storage_key, backend, voice_id, duration_seconds, chars_processed,
                webhook_url, webhook_sent_at, error, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, NULL, NULL, ?, NULL, NULL, ?, NULL)
            """,
            (
                job_id,
                article_id,
                text,
                text_hash,
                text_preview,
                audio_url,
                f"audio/{text_hash}.mp3",
                backend,
                voice_id,
                webhook_url,
                created_at,
            ),
        )

    return get_job_by_id(sqlite_path, job_id)


def get_job_by_id(sqlite_path: str, job_id: str) -> dict | None:
    with _connect(sqlite_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row)


def get_job_by_text_hash(sqlite_path: str, text_hash: str) -> dict | None:
    with _connect(sqlite_path) as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE text_hash = ? ORDER BY created_at DESC LIMIT 1",
            (text_hash,),
        ).fetchone()
    return _row_to_dict(row)


def get_job_by_article_id(sqlite_path: str, article_id: str) -> dict | None:
    with _connect(sqlite_path) as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE article_id = ? ORDER BY created_at DESC LIMIT 1",
            (article_id,),
        ).fetchone()
    return _row_to_dict(row)


def list_pending_jobs(sqlite_path: str, limit: int = 10) -> list[dict]:
    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_job_status(
    sqlite_path: str,
    job_id: str,
    new_status: str,
    *,
    completed_at: str | None = None,
    error: str | None = None,
    duration_seconds: float | None = None,
    chars_processed: int | None = None,
) -> dict | None:
    if new_status == "done" and completed_at is None:
        completed_at = _utc_now()

    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, completed_at = ?, error = ?, duration_seconds = ?, chars_processed = ?
            WHERE id = ?
            """,
            (
                new_status,
                completed_at,
                error,
                duration_seconds,
                chars_processed,
                job_id,
            ),
        )

    return get_job_by_id(sqlite_path, job_id)


def update_webhook_sent(sqlite_path: str, job_id: str, timestamp: str) -> dict | None:
    with _connect(sqlite_path) as conn:
        conn.execute(
            "UPDATE jobs SET webhook_sent_at = ? WHERE id = ?",
            (timestamp, job_id),
        )

    return get_job_by_id(sqlite_path, job_id)
