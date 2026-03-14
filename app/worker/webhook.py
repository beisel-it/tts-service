from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime

import httpx

from app.db.crud import update_webhook_sent
from app.db.models import JobRecord

logger = logging.getLogger(__name__)

# Tasks set to prevent GC of fire-and-forget tasks
_pending_tasks: set[asyncio.Task] = set()


def _build_payload(job: JobRecord) -> dict:
    return {
        "job_id": job.id,
        "article_id": job.article_id,
        "status": job.status,
        "audio_url": job.audio_url,
        "duration_seconds": job.duration_seconds,
        "error": job.error if job.status == "failed" else None,
    }


def _sign_payload(body_bytes: bytes, signing_secret: str) -> str:
    return hmac.new(
        signing_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()


async def _dispatch_with_retry(
    job: JobRecord,
    webhook_url: str,
    signing_secret: str,
    sqlite_path: str,
    timeout_seconds: int,
    retry_attempts: int,
) -> bool:
    payload = _build_payload(job)
    body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = _sign_payload(body_bytes, signing_secret)
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-TTS-Signature": signature,
    }

    backoff = [2, 5, 10]

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        for attempt in range(retry_attempts):
            try:
                resp = await client.post(
                    webhook_url,
                    content=body_bytes,
                    headers=headers,
                )
                if resp.status_code < 400:
                    ts = datetime.now(UTC).isoformat()
                    update_webhook_sent(sqlite_path, job.id, ts)
                    logger.info("Webhook delivered for job %s (attempt %d)", job.id, attempt + 1)
                    return True
                if resp.status_code < 500:
                    logger.warning(
                        "Webhook 4xx for job %s: %d — not retrying",
                        job.id,
                        resp.status_code,
                    )
                    return False
                # 5xx — retry
                logger.debug(
                    "Webhook 5xx for job %s: %d (attempt %d/%d)",
                    job.id,
                    resp.status_code,
                    attempt + 1,
                    retry_attempts,
                )
            except (httpx.NetworkError, httpx.TimeoutException) as exc:
                logger.debug(
                    "Webhook network error for job %s (attempt %d/%d): %s",
                    job.id,
                    attempt + 1,
                    retry_attempts,
                    exc,
                )

            if attempt < retry_attempts - 1:
                await asyncio.sleep(backoff[min(attempt, len(backoff) - 1)])

    logger.warning("Webhook all retries exhausted for job %s", job.id)
    return False


def dispatch_webhook(
    job: JobRecord,
    webhook_url: str,
    signing_secret: str,
    sqlite_path: str,
    timeout_seconds: int = 10,
    retry_attempts: int = 3,
) -> None:
    """Fire-and-forget webhook dispatch. Must be called from an async context."""
    task = asyncio.create_task(
        _dispatch_with_retry(
            job,
            webhook_url,
            signing_secret,
            sqlite_path,
            timeout_seconds,
            retry_attempts,
        )
    )
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)
