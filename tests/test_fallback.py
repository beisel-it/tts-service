"""Tests for the fallback backend logic (Task E2)."""
from __future__ import annotations

import asyncio
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.backends.base import AuthenticationError, NetworkError, RateLimitError
from app.backends.router import InvalidBackendError
from app.config import Config
from app.worker.worker import Worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(fallback_order: list[str] | None = None) -> Config:
    return Config(
        default_backend="elevenlabs",
        backend_fallback_order=fallback_order or ["elevenlabs"],
    )


def _make_job(**kwargs) -> dict:
    defaults = {
        "id": str(uuid.uuid4()),
        "text": "Hello fallback",
        "text_hash": "a" * 64,
        "voice_id": "v1",
        "backend": "elevenlabs",
        "article_id": None,
        "retry_count": 0,
        "created_at": "2024-01-01T00:00:00",
        "webhook_url": None,
    }
    defaults.update(kwargs)
    return defaults


def _backend_that_raises(exc: Exception) -> MagicMock:
    b = MagicMock()
    b.synthesize = AsyncMock(side_effect=exc)
    return b


def _backend_that_succeeds(audio: bytes = b"OK") -> MagicMock:
    b = MagicMock()
    b.synthesize = AsyncMock(return_value=audio)
    return b


def _router_for_order(backends: dict) -> MagicMock:
    router = MagicMock()

    def _get(name):
        if name not in backends:
            raise InvalidBackendError(f"Backend '{name}' not configured")
        return backends[name]

    router.get_backend.side_effect = _get
    return router


# ---------------------------------------------------------------------------
# Fallback: first backend fails recoverable, second succeeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_first_backend_fails_second_succeeds():
    b1 = _backend_that_raises(RateLimitError("rate limited", retry_after=10))
    b2 = _backend_that_succeeds(audio=b"AUDIO_FROM_B2")

    router = _router_for_order({"elevenlabs": b1, "azure": b2})
    storage = MagicMock()
    storage.write_audio.return_value = "http://x/a.mp3"
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    cfg = _config(fallback_order=["elevenlabs", "azure"])
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=cfg)

    job = _make_job()
    await worker._process_job(job)

    queue_mock.complete_job.assert_called_once()
    call = queue_mock.complete_job.call_args
    assert call[1]["backend_used"] == "azure"
    assert call[1]["backends_tried"] == ["elevenlabs", "azure"]
    queue_mock.fail_job.assert_not_called()


@pytest.mark.asyncio
async def test_fallback_network_error_tries_next():
    b1 = _backend_that_raises(NetworkError("timeout"))
    b2 = _backend_that_succeeds()

    router = _router_for_order({"elevenlabs": b1, "polly": b2})
    storage = MagicMock()
    storage.write_audio.return_value = "http://x/a.mp3"
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    cfg = _config(fallback_order=["elevenlabs", "polly"])
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=cfg)

    await worker._process_job(_make_job())

    queue_mock.complete_job.assert_called_once()
    assert queue_mock.complete_job.call_args[1]["backend_used"] == "polly"


# ---------------------------------------------------------------------------
# Non-recoverable error: no fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonfatal_error_skips_fallback():
    b1 = _backend_that_raises(AuthenticationError("invalid key"))
    b2 = _backend_that_succeeds()

    router = _router_for_order({"elevenlabs": b1, "azure": b2})
    queue_mock = MagicMock()
    queue_mock.fail_job = MagicMock()

    cfg = _config(fallback_order=["elevenlabs", "azure"])
    worker = Worker(queue=queue_mock, router=router, storage=MagicMock(), config=cfg)

    await worker._process_job(_make_job())

    queue_mock.fail_job.assert_called_once()
    _, kwargs = queue_mock.fail_job.call_args
    assert kwargs["force_permanent"] is True
    # b2 should never have been attempted
    b2.synthesize.assert_not_called()


# ---------------------------------------------------------------------------
# All backends exhausted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_backends_exhausted_causes_fail_job():
    b1 = _backend_that_raises(NetworkError("b1 down"))
    b2 = _backend_that_raises(RateLimitError("b2 rate limited"))
    b3 = _backend_that_raises(NetworkError("b3 down"))

    router = _router_for_order({"elevenlabs": b1, "azure": b2, "polly": b3})
    queue_mock = MagicMock()
    queue_mock.fail_job = MagicMock()

    cfg = _config(fallback_order=["elevenlabs", "azure", "polly"])
    worker = Worker(queue=queue_mock, router=router, storage=MagicMock(), config=cfg)

    await worker._process_job(_make_job())

    queue_mock.fail_job.assert_called_once()
    pos_args, kwargs = queue_mock.fail_job.call_args
    assert kwargs.get("backends_tried") == ["elevenlabs", "azure", "polly"]
    assert kwargs.get("force_permanent") is False  # retryable


# ---------------------------------------------------------------------------
# Custom fallback order
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_fallback_order_is_respected():
    call_order = []

    async def synth_fail(**kwargs):
        raise NetworkError("down")

    async def synth_ok(**kwargs):
        return b"OK"

    b_polly = MagicMock()
    b_polly.synthesize = AsyncMock(side_effect=synth_fail)
    b_azure = MagicMock()
    b_azure.synthesize = AsyncMock(side_effect=synth_ok)

    router = _router_for_order({"polly": b_polly, "azure": b_azure})
    storage = MagicMock()
    storage.write_audio.return_value = "http://x/a.mp3"
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    # polly first, azure second (reversed from default)
    cfg = _config(fallback_order=["polly", "azure"])
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=cfg)

    await worker._process_job(_make_job())

    assert queue_mock.complete_job.call_args[1]["backend_used"] == "azure"
    assert queue_mock.complete_job.call_args[1]["backends_tried"] == ["polly", "azure"]


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_logging_structured(caplog):
    b1 = _backend_that_raises(RateLimitError("rate limited"))
    b2 = _backend_that_succeeds()

    router = _router_for_order({"elevenlabs": b1, "azure": b2})
    storage = MagicMock()
    storage.write_audio.return_value = "http://x/a.mp3"
    queue_mock = MagicMock()
    queue_mock.complete_job = MagicMock(return_value=True)

    cfg = _config(fallback_order=["elevenlabs", "azure"])
    worker = Worker(queue=queue_mock, router=router, storage=storage, config=cfg)

    with caplog.at_level(logging.WARNING, logger="app.worker.worker"):
        await worker._process_job(_make_job())

    # Should log a fallback warning
    messages = [r.message for r in caplog.records]
    assert any("elevenlabs" in m and ("recoverable" in m.lower() or "fallback" in m.lower()) for m in messages)


@pytest.mark.asyncio
async def test_all_backends_exhausted_logged_as_error(caplog):
    b1 = _backend_that_raises(NetworkError("down"))
    router = _router_for_order({"elevenlabs": b1})
    queue_mock = MagicMock()
    queue_mock.fail_job = MagicMock()

    cfg = _config(fallback_order=["elevenlabs"])
    worker = Worker(queue=queue_mock, router=router, storage=MagicMock(), config=cfg)

    with caplog.at_level(logging.ERROR, logger="app.worker.worker"):
        await worker._process_job(_make_job())

    messages = [r.message for r in caplog.records]
    assert any("exhausted" in m.lower() or "all backends" in m.lower() for m in messages)
