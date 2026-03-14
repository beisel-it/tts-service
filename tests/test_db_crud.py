from __future__ import annotations

from app.db.crud import (
    create_job,
    get_job_by_article_id,
    get_job_by_text_hash,
    list_pending_jobs,
    update_job_status,
)
from app.db.schema import init_db


def test_create_job_inserts_correct_fields(configured_env):
    db_path = str(configured_env["db_path"])
    init_db(db_path)

    job = create_job(
        db_path,
        text="Hallo Welt",
        text_hash="hash1",
        article_id="article-1",
        audio_url="https://audio.example.com/audio/hash1.mp3",
        backend="elevenlabs",
        voice_id="voice1",
        webhook_url=None,
    )

    assert job["status"] == "pending"
    assert job["text_hash"] == "hash1"
    assert job["article_id"] == "article-1"


def test_get_job_by_text_hash_returns_existing(configured_env):
    db_path = str(configured_env["db_path"])
    init_db(db_path)

    create_job(
        db_path,
        text="Same text",
        text_hash="same-hash",
        article_id=None,
        audio_url="https://audio.example.com/audio/same-hash.mp3",
        backend="elevenlabs",
        voice_id="voice1",
        webhook_url=None,
    )

    found = get_job_by_text_hash(db_path, "same-hash")
    assert found is not None
    assert found["text"] == "Same text"


def test_list_pending_jobs_respects_limit_and_order(configured_env):
    db_path = str(configured_env["db_path"])
    init_db(db_path)

    first = create_job(
        db_path,
        text="First",
        text_hash="h1",
        article_id="a1",
        audio_url="https://audio.example.com/audio/h1.mp3",
        backend="elevenlabs",
        voice_id="voice1",
        webhook_url=None,
    )
    second = create_job(
        db_path,
        text="Second",
        text_hash="h2",
        article_id="a2",
        audio_url="https://audio.example.com/audio/h2.mp3",
        backend="elevenlabs",
        voice_id="voice1",
        webhook_url=None,
    )

    pending = list_pending_jobs(db_path, limit=1)
    assert len(pending) == 1
    assert pending[0]["id"] == first["id"]
    assert pending[0]["id"] != second["id"]


def test_update_status_sets_completed_at_on_done(configured_env):
    db_path = str(configured_env["db_path"])
    init_db(db_path)

    job = create_job(
        db_path,
        text="Done me",
        text_hash="done-hash",
        article_id="done-1",
        audio_url="https://audio.example.com/audio/done-hash.mp3",
        backend="elevenlabs",
        voice_id="voice1",
        webhook_url=None,
    )

    updated = update_job_status(db_path, job["id"], "done")
    assert updated is not None
    assert updated["status"] == "done"
    assert updated["completed_at"] is not None

    by_article = get_job_by_article_id(db_path, "done-1")
    assert by_article is not None
    assert by_article["id"] == job["id"]
