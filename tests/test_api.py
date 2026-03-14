from __future__ import annotations

import hashlib

from app.config import get_settings
from app.db.crud import create_job, update_job_status


def test_synthesize_new_returns_201(client):
    response = client.post(
        "/synthesize",
        json={"text": "Hello world", "article_id": "article-123"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "pending"
    assert payload["job_id"].startswith("tts_")
    assert payload["audio_url"].startswith("https://audio.example.com/audio/")
    assert payload["poll_url"].startswith("http://testserver/jobs/")
    assert payload["cached"] is False


def test_synthesize_cached_text_hash_returns_200(client):
    settings = get_settings()
    text = "Duplicate text"
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    existing = create_job(
        settings.sqlite_path,
        text=text,
        text_hash=text_hash,
        article_id=None,
        audio_url=f"https://audio.example.com/audio/{text_hash}.mp3",
        backend="elevenlabs",
        voice_id="test-voice",
        webhook_url=None,
    )
    update_job_status(settings.sqlite_path, existing["id"], "done")

    response = client.post("/synthesize", json={"text": text})

    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is True
    assert payload["job_id"] == existing["id"]


def test_synthesize_cached_article_returns_200(client):
    settings = get_settings()
    existing = create_job(
        settings.sqlite_path,
        text="Original",
        text_hash="abc123",
        article_id="article-cached",
        audio_url="https://audio.example.com/audio/abc123.mp3",
        backend="elevenlabs",
        voice_id="test-voice",
        webhook_url=None,
    )
    update_job_status(settings.sqlite_path, existing["id"], "done")

    response = client.post(
        "/synthesize",
        json={"text": "Different text but same article", "article_id": "article-cached"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is True
    assert payload["job_id"] == existing["id"]


def test_synthesize_validates_empty_text(client):
    response = client.post("/synthesize", json={"text": "   "})
    assert response.status_code == 422


def test_synthesize_rejects_invalid_backend(client):
    response = client.post(
        "/synthesize",
        json={"text": "Hello", "backend": "unsupported"},
    )
    assert response.status_code == 422
