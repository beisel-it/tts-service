"""Tests for the SQLite job queue (Task C1)."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.worker.queue import JobNotFoundError, Queue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job_id() -> str:
    return str(uuid.uuid4())


def _insert_job(queue: Queue, job_id: str | None = None, text: str = "Hello") -> str:
    """Insert a pending job directly via the internal connection helper."""
    jid = job_id or _make_job_id()
    import sqlite3
    conn = sqlite3.connect(queue._db_path)
    conn.execute(
        """INSERT INTO jobs (id, text, text_hash, voice_id, backend, article_id, retry_count, status)
           VALUES (?, ?, ?, ?, ?, ?, 0, 'pending')""",
        (jid, text, "hash_" + jid[:8], "voice1", "elevenlabs", None),
    )
    conn.commit()
    conn.close()
    return jid


# ---------------------------------------------------------------------------
# claim_next_job
# ---------------------------------------------------------------------------


def test_claim_next_job_returns_none_when_empty(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    assert q.claim_next_job() is None


def test_claim_next_job_returns_job(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    job = q.claim_next_job()
    assert job is not None
    assert job["id"] == jid
    assert job["text"] == "Hello"


def test_claim_next_job_sets_status_to_processing(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    q.claim_next_job()
    status = q.get_job_status(jid)
    assert status["status"] == "processing"


def test_claim_next_job_is_atomic_no_double_pickup(tmp_path: Path):
    """Two consecutive claim calls must not return the same job."""
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    job1 = q.claim_next_job()
    job2 = q.claim_next_job()
    assert job1 is not None
    assert job1["id"] == jid
    assert job2 is None  # second claim finds no pending job


def test_claim_next_job_fifo_order(tmp_path: Path):
    """Oldest job (by created_at) must be returned first."""
    q = Queue(str(tmp_path / "jobs.db"))
    import time, sqlite3
    conn = sqlite3.connect(q._db_path)
    jid1 = _make_job_id()
    jid2 = _make_job_id()
    conn.execute(
        "INSERT INTO jobs (id, text, text_hash, status, created_at) VALUES (?, 'a', 'h1', 'pending', '2024-01-01T10:00:00')",
        (jid1,),
    )
    conn.execute(
        "INSERT INTO jobs (id, text, text_hash, status, created_at) VALUES (?, 'b', 'h2', 'pending', '2024-01-01T11:00:00')",
        (jid2,),
    )
    conn.commit()
    conn.close()

    job = q.claim_next_job()
    assert job["id"] == jid1


# ---------------------------------------------------------------------------
# complete_job
# ---------------------------------------------------------------------------


def test_complete_job_sets_status_done(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    q.claim_next_job()
    q.complete_job(jid, duration_seconds=1.5, audio_url="http://example.com/a.mp3")
    status = q.get_job_status(jid)
    assert status["status"] == "done"


def test_complete_job_stores_audio_url_and_duration(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    q.claim_next_job()
    q.complete_job(jid, duration_seconds=2.0, audio_url="http://x/y.mp3", backend_used="elevenlabs")
    status = q.get_job_status(jid)
    assert status["audio_url"] == "http://x/y.mp3"
    assert status["duration_seconds"] == pytest.approx(2.0)
    assert status["backend"] == "elevenlabs"


def test_complete_job_raises_for_unknown_id(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    with pytest.raises(JobNotFoundError):
        q.complete_job("nonexistent", duration_seconds=1.0)


def test_complete_job_returns_true(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    q.claim_next_job()
    result = q.complete_job(jid, duration_seconds=0.5)
    assert result is True


# ---------------------------------------------------------------------------
# fail_job
# ---------------------------------------------------------------------------


def test_fail_job_increments_retry_count(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"), max_retries=3)
    jid = _insert_job(q)
    q.claim_next_job()
    success, retry_count = q.fail_job(jid, "transient error")
    assert success is True
    assert retry_count == 1
    status = q.get_job_status(jid)
    assert status["status"] == "pending"


def test_fail_job_permanent_after_max_retries(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"), max_retries=3)
    jid = _insert_job(q)
    q.claim_next_job()
    q.fail_job(jid, "err1")  # retry_count → 1, pending
    q.claim_next_job()
    q.fail_job(jid, "err2")  # retry_count → 2, pending
    q.claim_next_job()
    _, retry_count = q.fail_job(jid, "err3")  # retry_count → 3 → failed
    assert retry_count == 3
    status = q.get_job_status(jid)
    assert status["status"] == "failed"


def test_fail_job_force_permanent(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    q.claim_next_job()
    _, retry_count = q.fail_job(jid, "auth error", force_permanent=True)
    status = q.get_job_status(jid)
    assert status["status"] == "failed"
    assert retry_count == 1


def test_fail_job_stores_error_message(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    q.claim_next_job()
    q.fail_job(jid, "Something went wrong", force_permanent=True)
    status = q.get_job_status(jid)
    assert "Something went wrong" in status["error"]


def test_fail_job_raises_for_unknown_id(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    with pytest.raises(JobNotFoundError):
        q.fail_job("nonexistent", "error")


# ---------------------------------------------------------------------------
# get_job_status
# ---------------------------------------------------------------------------


def test_get_job_status_returns_none_for_unknown(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    assert q.get_job_status("no-such-id") is None


def test_get_job_status_reflects_current_state(tmp_path: Path):
    q = Queue(str(tmp_path / "jobs.db"))
    jid = _insert_job(q)
    status = q.get_job_status(jid)
    assert status["status"] == "pending"


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_queue_usable_as_context_manager(tmp_path: Path):
    with Queue(str(tmp_path / "jobs.db")) as q:
        assert q.claim_next_job() is None


# ---------------------------------------------------------------------------
# Import check
# ---------------------------------------------------------------------------


def test_module_importable():
    from app.worker.queue import Queue as Q  # noqa: F401
