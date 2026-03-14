from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.db.models import JobRecord
from app.worker.webhook import _build_payload, _dispatch_with_retry, _sign_payload


def _make_job(**kwargs) -> JobRecord:
    defaults = dict(
        id="tts_abc12345",
        article_id="art-1",
        text="Hello world",
        text_hash="deadbeef",
        text_preview="Hello world",
        status="done",
        audio_url="https://audio.example.com/audio/deadbeef.mp3",
        storage_key="audio/deadbeef.mp3",
        backend="elevenlabs",
        voice_id="test-voice",
        duration_seconds=3.5,
        chars_processed=11,
        webhook_url=None,
        webhook_sent_at=None,
        error=None,
        created_at="2026-03-14T10:00:00+00:00",
        completed_at="2026-03-14T10:00:03+00:00",
    )
    defaults.update(kwargs)
    return JobRecord(**defaults)


# ---------------------------------------------------------------------------
# Signature tests
# ---------------------------------------------------------------------------


def test_sign_payload_produces_valid_hmac():
    secret = "mysecret"
    body = b'{"job_id":"tts_abc"}'
    sig = _sign_payload(body, secret)
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sig == expected


def test_sign_payload_different_secret_differs():
    body = b'{"job_id":"tts_abc"}'
    sig1 = _sign_payload(body, "secret1")
    sig2 = _sign_payload(body, "secret2")
    assert sig1 != sig2


def test_build_payload_done_job():
    job = _make_job(status="done", error=None)
    payload = _build_payload(job)
    assert payload["job_id"] == "tts_abc12345"
    assert payload["article_id"] == "art-1"
    assert payload["status"] == "done"
    assert payload["audio_url"] == "https://audio.example.com/audio/deadbeef.mp3"
    assert payload["duration_seconds"] == 3.5
    assert payload["error"] is None


def test_build_payload_failed_job_includes_error():
    job = _make_job(status="failed", error="synthesis failed", duration_seconds=None)
    payload = _build_payload(job)
    assert payload["status"] == "failed"
    assert payload["error"] == "synthesis failed"


def test_build_payload_done_job_omits_error():
    job = _make_job(status="done", error="leftover error")
    payload = _build_payload(job)
    assert payload["error"] is None


def test_payload_is_stable_sorted():
    job = _make_job(status="done")
    payload = _build_payload(job)
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    body2 = json.dumps(payload, sort_keys=True).encode("utf-8")
    assert body == body2


# ---------------------------------------------------------------------------
# Retry / dispatch tests
# ---------------------------------------------------------------------------


def test_dispatch_success_on_first_attempt(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    job = _make_job(status="done")
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 200
        return resp

    with patch("app.worker.webhook.update_webhook_sent") as mock_update, \
         patch("httpx.AsyncClient.post", new=mock_post):
        result = asyncio.run(
            _dispatch_with_retry(job, "https://example.com/webhook", "secret", db_path, 5, 3)
        )

    assert result is True
    mock_update.assert_called_once()


def test_dispatch_no_retry_on_4xx(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    job = _make_job(status="done")
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 404
        return resp

    with patch("app.worker.webhook.update_webhook_sent") as mock_update, \
         patch("httpx.AsyncClient.post", new=mock_post):
        result = asyncio.run(
            _dispatch_with_retry(job, "https://example.com/webhook", "secret", db_path, 5, 3)
        )

    assert result is False
    assert call_count == 1
    mock_update.assert_not_called()


def test_dispatch_retries_on_5xx_then_succeeds(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    job = _make_job(status="done")
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.status_code = 500 if call_count < 2 else 200
        return resp

    with patch("app.worker.webhook.update_webhook_sent") as mock_update, \
         patch("asyncio.sleep", new=AsyncMock()), \
         patch("httpx.AsyncClient.post", new=mock_post):
        result = asyncio.run(
            _dispatch_with_retry(job, "https://example.com/webhook", "secret", db_path, 5, 3)
        )

    assert result is True
    assert call_count == 2
    mock_update.assert_called_once()


def test_dispatch_exhausts_retries_on_network_error(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    job = _make_job(status="done")
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.NetworkError("connection refused")

    with patch("app.worker.webhook.update_webhook_sent") as mock_update, \
         patch("asyncio.sleep", new=AsyncMock()), \
         patch("httpx.AsyncClient.post", new=mock_post):
        result = asyncio.run(
            _dispatch_with_retry(job, "https://example.com/webhook", "secret", db_path, 5, 3)
        )

    assert result is False
    assert call_count == 3
    mock_update.assert_not_called()
