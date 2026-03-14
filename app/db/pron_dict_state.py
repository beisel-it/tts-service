from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PronDictState:
    owner_key_hash: str
    dictionary_id: str
    version_id: str
    last_pls_hash: str
    updated_at: str


def get_state(sqlite_path: str, *, owner_key_hash: str) -> PronDictState | None:
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM pronunciation_dict_state WHERE owner_key_hash = ?",
            (owner_key_hash,),
        ).fetchone()
        if row is None:
            return None
        return PronDictState(
            owner_key_hash=row["owner_key_hash"],
            dictionary_id=row["dictionary_id"],
            version_id=row["version_id"],
            last_pls_hash=row["last_pls_hash"],
            updated_at=row["updated_at"],
        )


def upsert_state(
    sqlite_path: str,
    *,
    owner_key_hash: str,
    dictionary_id: str,
    version_id: str,
    last_pls_hash: str,
) -> PronDictState:
    now = _utcnow()
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO pronunciation_dict_state (
                owner_key_hash, dictionary_id, version_id, last_pls_hash, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(owner_key_hash) DO UPDATE SET
                dictionary_id = excluded.dictionary_id,
                version_id = excluded.version_id,
                last_pls_hash = excluded.last_pls_hash,
                updated_at = excluded.updated_at
            """,
            (owner_key_hash, dictionary_id, version_id, last_pls_hash, now),
        )

    return PronDictState(
        owner_key_hash=owner_key_hash,
        dictionary_id=dictionary_id,
        version_id=version_id,
        last_pls_hash=last_pls_hash,
        updated_at=now,
    )
