from __future__ import annotations

import hashlib
import math

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, HttpUrl, field_validator

from app.config import get_settings
from app.db.crud import (
    create_job,
    get_job_by_article_id,
    get_job_by_text_hash,
)
from app.middleware.auth import verify_api_key

router = APIRouter()


class SynthesizeRequest(BaseModel):
    text: str
    article_id: str | None = None
    voice: str | None = None
    backend: str | None = None
    webhook_url: HttpUrl | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must not be empty")
        return normalized


class SynthesizeResponse(BaseModel):
    job_id: str
    status: str
    audio_url: str
    poll_url: str
    estimated_seconds: int
    cached: bool = False


@router.post(
    "/synthesize",
    response_model=SynthesizeResponse,
    status_code=201,
    dependencies=[Depends(verify_api_key)],
)
def synthesize(payload: SynthesizeRequest, response: Response) -> SynthesizeResponse:
    settings = get_settings()

    if len(payload.text) > settings.max_text_length:
        raise HTTPException(
            status_code=422,
            detail=f"text exceeds max length of {settings.max_text_length}",
        )

    backend = payload.backend or settings.backends.default_backend
    if backend not in settings.backends.enabled:
        raise HTTPException(status_code=422, detail=f"unsupported backend: {backend}")

    voice_id = payload.voice or settings.backends.elevenlabs.default_voice
    text_hash = hashlib.sha256(payload.text.encode("utf-8")).hexdigest()

    existing = None
    if payload.article_id:
        existing = get_job_by_article_id(settings.sqlite_path, payload.article_id)
        if existing and existing["status"] == "done":
            response.status_code = 200
            return SynthesizeResponse(
                job_id=existing["id"],
                status=existing["status"],
                audio_url=existing["audio_url"],
                poll_url=f"{settings.api_base_url.rstrip('/')}/jobs/{existing['id']}",
                estimated_seconds=max(1, math.ceil(len(payload.text) / 30)),
                cached=True,
            )

    existing = get_job_by_text_hash(settings.sqlite_path, text_hash)
    if existing and existing["status"] == "done":
        response.status_code = 200
        return SynthesizeResponse(
            job_id=existing["id"],
            status=existing["status"],
            audio_url=existing["audio_url"],
            poll_url=f"{settings.api_base_url.rstrip('/')}/jobs/{existing['id']}",
            estimated_seconds=max(1, math.ceil(len(payload.text) / 30)),
            cached=True,
        )

    audio_url = settings.get_audio_url(text_hash)
    job = create_job(
        settings.sqlite_path,
        text=payload.text,
        text_hash=text_hash,
        article_id=payload.article_id,
        audio_url=audio_url,
        backend=backend,
        voice_id=voice_id,
        webhook_url=str(payload.webhook_url) if payload.webhook_url else None,
    )

    return SynthesizeResponse(
        job_id=job["id"],
        status=job["status"],
        audio_url=job["audio_url"],
        poll_url=f"{settings.api_base_url.rstrip('/')}/jobs/{job['id']}",
        estimated_seconds=max(1, math.ceil(len(payload.text) / 30)),
        cached=False,
    )
