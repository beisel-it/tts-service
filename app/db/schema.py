from __future__ import annotations

import sqlite3
from pathlib import Path


def init_db(sqlite_path: str) -> None:
    db_path = Path(sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                article_id TEXT,
                text TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                text_preview TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'processing', 'done', 'failed')),
                audio_url TEXT NOT NULL,
                storage_key TEXT,
                backend TEXT,
                voice_id TEXT,
                duration_seconds REAL,
                chars_processed INTEGER,
                webhook_url TEXT,
                webhook_sent_at TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_text_hash ON jobs(text_hash)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_article_id ON jobs(article_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pronunciations (
                id TEXT PRIMARY KEY,
                owner_key_hash TEXT NOT NULL,
                language TEXT NOT NULL,
                grapheme TEXT NOT NULL,
                alias TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_key_hash, language, grapheme)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prn_owner_lang ON pronunciations(owner_key_hash, language)"
        )
