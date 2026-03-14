"""Tests for the worker loop (Task C2)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.backends.base import AuthenticationError, NetworkError, RateLimitError
from app.config import Config
from app.worker.worker import Worker
from app.worker.queue import Queue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**kwargs) -> Config:
    defaults = {
        "default_backend": "elevenlabs",
        "backend_fallback_order": ["elevenlabs"],
    }
    defaults.update(kwargs)
    return Config(**defaults)


def _mock_router(audio_bytes: bytes = b"MP3") -> MagicMock:
    backend = MagicMock()
    backend.synthesize = AsyncMock(return_value=audio_bytes)
    router = MagicMock()
    router.get_backend.return_value = backend
    return router


def _mock_storage(audio_url: str = "http://example.com/audio.mp3") -> MagicMock:
    storage = MagicMock()
    storage.write_audio.return_value = audio_url
    return storage


def _make_job(job_id: str | None = None, text: str = "Hello", voice_id: str = "v1", webhook_url: str | None = None) -> dict:
    return {
        "id": job_id or str(uuid.uuid4()),
        "text": text,
        "text_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
        "voice_id": voice_id,
        "backend": "elevenlabs",
        "article_id": None,
        "retry_count": 0,
        "created_at": "2024-01-01T00:00:00",
        "webhook_url": webhook_url,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_processes_job_and_marks_done(tmp_path: Path):
    queue = Queue(str(tmp_path / "jobs.db"))
    router = _mock_router(audio_bytes=b"AUDIO")
    storage = _mock_storage(audio_url="http://x/a.mp3")
    cfg = _config()

    job = _make_job()
    queue_mock = MagicMock()
    queue_mock.claim_next_job.side_effect = [job, None]  # one job, then empty
    queue_mock.complete_job = MagicMock(return_value=True)
    queue_mock.fail_job = MagicMock()

    worker = Worker(queue=queue_mock, router=router, storage=storage, config=cfg)
    worker.request_shutdown()  # stop after first iteration where queue is empty
    # But we need to process the job first — reset shutdown so loop runs twice
    worker._shutdown_requested = False

    # Run two iterations: first gets job and processes, second gets None and shuts down
    call_count = 0
    original_claim = queue_mock.claim_next_job.side_effect

    async def run_limited():
        # patch sleep to avoid waiting
        with patch("asyncio.sleep", new_callable=AsyncMock):
            # Override shutdown after processing first job
            job_processed = asyncio.Event()

            original_process = worker._process_job

            async def patched_process(job):
                await original_process(job)
                worker.request_shutdown()

            worker._process_job = patched_process
            await worker.run()

    await run_limited()

    queue_mock.complete_job.assert_called_once()
    call_args = queue_mock.complete_job.call_args
    assert call_args[0][0] == job["id"]
    queue_mock.fail_job.assert_not_called()


@pytest.mark.asyncio
async def test_happy_path_calls_storage_write(tmp_path: Path):
    router = _mock_router(audio_bytes=b"BYTES")
    storage = _mock_storage()
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    job = _make_job()
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=_config())
    await worker._process_job(job)

    storage.write_audio.assert_called_once_with(b"BYTES", job["text_hash"])


@pytest.mark.asyncio
async def test_happy_path_complete_job_receives_correct_args():
    router = _mock_router(audio_bytes=b"BYTES")
    storage = _mock_storage(audio_url="http://x/audio.mp3")
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    job = _make_job(text="Test text")
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=_config())
    await worker._process_job(job)

    call = queue_mock.complete_job.call_args
    assert call[1]["audio_url"] == "http://x/audio.mp3"
    assert call[1]["chars_processed"] == len("Test text")
    assert call[1]["backend_used"] == "elevenlabs"


# ---------------------------------------------------------------------------
# Storage failure → permanent fail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_storage_write_error_causes_permanent_fail():
    router = _mock_router()
    storage = MagicMock()
    storage.write_audio.side_effect = OSError("Disk full")
    queue_mock = MagicMock()
    queue_mock.fail_job = MagicMock()

    job = _make_job()
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=_config())
    await worker._process_job(job)

    queue_mock.fail_job.assert_called_once()
    _, kwargs = queue_mock.fail_job.call_args
    assert kwargs["force_permanent"] is True


# ---------------------------------------------------------------------------
# Non-recoverable backend error → permanent fail, no fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_recoverable_error_causes_permanent_fail_no_fallback():
    backend = MagicMock()
    backend.synthesize = AsyncMock(side_effect=AuthenticationError("bad key"))
    router = MagicMock()
    router.get_backend.return_value = backend
    queue_mock = MagicMock()
    queue_mock.fail_job = MagicMock()

    job = _make_job()
    cfg = _config(backend_fallback_order=["elevenlabs", "azure"])
    worker = Worker(queue=queue_mock, router=router, storage=MagicMock(), config=cfg)
    await worker._process_job(job)

    queue_mock.fail_job.assert_called_once()
    _, kwargs = queue_mock.fail_job.call_args
    assert kwargs["force_permanent"] is True
    # Should have stopped after first backend — no fallback for auth errors
    assert router.get_backend.call_count == 1


# ---------------------------------------------------------------------------
# Webhook dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_dispatched_after_completion():
    router = _mock_router()
    storage = _mock_storage(audio_url="http://x/a.mp3")
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    dispatched = []

    async def fake_dispatch(job_id, audio_url, webhook_url):
        dispatched.append((job_id, audio_url, webhook_url))

    job = _make_job(webhook_url="http://webhook.example.com/notify")
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=_config())
    worker._dispatch_webhook = fake_dispatch

    await worker._process_job(job)

    # Give the task a chance to run
    await asyncio.sleep(0)

    assert len(dispatched) == 1
    assert dispatched[0][0] == job["id"]
    assert dispatched[0][2] == "http://webhook.example.com/notify"


@pytest.mark.asyncio
async def test_no_webhook_when_webhook_url_is_none():
    router = _mock_router()
    storage = _mock_storage()
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    dispatched = []

    async def fake_dispatch(job_id, audio_url, webhook_url):
        dispatched.append(job_id)

    job = _make_job(webhook_url=None)
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=_config())
    worker._dispatch_webhook = fake_dispatch

    await worker._process_job(job)
    await asyncio.sleep(0)

    assert dispatched == []


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graceful_shutdown_stops_loop():
    """Worker should stop polling when request_shutdown() is called mid-loop."""
    queue_mock = MagicMock()
    claim_calls = 0

    def claim():
        nonlocal claim_calls
        claim_calls += 1
        if claim_calls >= 2:
            # On second call, trigger shutdown
            worker.request_shutdown()
        return None

    queue_mock.claim_next_job.side_effect = claim

    worker = Worker(
        queue=queue_mock,
        router=MagicMock(),
        storage=MagicMock(),
        config=_config(),
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await worker.run()

    # Worker entered the loop at least twice before shutting down
    assert claim_calls >= 2


# ---------------------------------------------------------------------------
# Module importable
# ---------------------------------------------------------------------------


def test_worker_module_importable():
    from app.worker.worker import Worker as W  # noqa: F401
