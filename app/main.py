from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.api.routes_admin import admin_router
from app.api.routes_pronunciations import admin_router as pronunciations_admin_router
from app.config import get_settings
from app.db.schema import init_db
from app.storage.local import init_storage

_DESCRIPTION = """
**tts-service** converts text to speech via configurable TTS backends (e.g. ElevenLabs).

## Authentication

All endpoints (except `GET /health`) require an API key passed in the
`X-API-Key` request header.

## Workflow

1. **POST /synthesize** — submit a text-to-speech job. Returns a `job_id` and a
   `poll_url` immediately; audio is generated asynchronously.
2. **GET /jobs/{job_id}** — poll until `status` is `done`, then fetch the audio
   from `audio_url`.

## Caching

Identical text (same SHA-256 hash) or the same `article_id` is served from
cache if a completed job already exists — the response will contain
`"cached": true` and HTTP 200 instead of 201.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.sqlite_path)
    init_storage()
    yield


app = FastAPI(
    title="tts-service",
    version="1.0.0",
    description=_DESCRIPTION,
    contact={
        "name": "Beisel IT",
        "email": "info@beisel.it",
    },
    license_info={
        "name": "Private",
    },
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(admin_router)
app.include_router(pronunciations_admin_router)
