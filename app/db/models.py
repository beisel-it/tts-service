from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


JobStatus = Literal["pending", "processing", "done", "failed"]


class JobRecord(BaseModel):
    id: str
    article_id: str | None = None
    text: str
    text_hash: str
    text_preview: str | None = None
    status: JobStatus
    audio_url: str
    storage_key: str | None = None
    backend: str | None = None
    voice_id: str | None = None
    duration_seconds: float | None = None
    chars_processed: int | None = None
    webhook_url: str | None = None
    webhook_sent_at: str | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None
