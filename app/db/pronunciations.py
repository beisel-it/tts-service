from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Pronunciation:
    id: str
    owner_key_hash: str
    language: str
    grapheme: str
    alias: str
    created_at: str
    updated_at: str


def list_pronunciations(sqlite_path: str, *, owner_key_hash: str, language: str | None) -> list[Pronunciation]:
    where = "WHERE owner_key_hash = ?"
    params: list[object] = [owner_key_hash]
    if language:
        where += " AND language = ?"
        params.append(language)

    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM pronunciations {where} ORDER BY language, grapheme",
            params,
        ).fetchall()

    return [
        Pronunciation(
            id=r["id"],
            owner_key_hash=r["owner_key_hash"],
            language=r["language"],
            grapheme=r["grapheme"],
            alias=r["alias"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


def create_pronunciation(
    sqlite_path: str,
    *,
    prn_id: str,
    owner_key_hash: str,
    language: str,
    grapheme: str,
    alias: str,
) -> Pronunciation:
    now = _utcnow()
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO pronunciations (
                id, owner_key_hash, language, grapheme, alias, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (prn_id, owner_key_hash, language, grapheme, alias, now, now),
        )

    return Pronunciation(
        id=prn_id,
        owner_key_hash=owner_key_hash,
        language=language,
        grapheme=grapheme,
        alias=alias,
        created_at=now,
        updated_at=now,
    )


def update_pronunciation(
    sqlite_path: str,
    *,
    prn_id: str,
    owner_key_hash: str,
    alias: str,
) -> Pronunciation | None:
    now = _utcnow()
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            UPDATE pronunciations
            SET alias = ?, updated_at = ?
            WHERE id = ? AND owner_key_hash = ?
            """,
            (alias, now, prn_id, owner_key_hash),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM pronunciations WHERE id = ?",
            (prn_id,),
        ).fetchone()

    assert row is not None
    return Pronunciation(
        id=row["id"],
        owner_key_hash=row["owner_key_hash"],
        language=row["language"],
        grapheme=row["grapheme"],
        alias=row["alias"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def delete_pronunciation(sqlite_path: str, *, prn_id: str, owner_key_hash: str) -> bool:
    with sqlite3.connect(sqlite_path) as conn:
        cur = conn.execute(
            "DELETE FROM pronunciations WHERE id = ? AND owner_key_hash = ?",
            (prn_id, owner_key_hash),
        )
        return cur.rowcount > 0
