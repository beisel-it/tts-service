from __future__ import annotations

from app.config import get_settings
from app.db.crud import create_job, update_job_status


def test_get_job_returns_full_record(client):
    settings = get_settings()
    job = create_job(
        settings.sqlite_path,
        text="Hello world",
        text_hash="abc123def456",
        article_id="art-1",
        audio_url="https://audio.example.com/audio/abc123def456.mp3",
        backend="elevenlabs",
        voice_id="test-voice",
        webhook_url=None,
    )

    response = client.get(f"/jobs/{job['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job["id"]
    assert data["status"] == "pending"
    assert data["text"] == "Hello world"
    assert data["article_id"] == "art-1"
    assert data["audio_url"] == "https://audio.example.com/audio/abc123def456.mp3"
    assert data["backend"] == "elevenlabs"
    assert data["voice_id"] == "test-voice"
    assert data["created_at"] is not None


def test_get_job_done_has_completed_at(client):
    settings = get_settings()
    job = create_job(
        settings.sqlite_path,
        text="Completed job",
        text_hash="done123",
        article_id=None,
        audio_url="https://audio.example.com/audio/done123.mp3",
        backend="elevenlabs",
        voice_id="test-voice",
        webhook_url=None,
    )
    update_job_status(
        settings.sqlite_path,
        job["id"],
        "done",
        duration_seconds=3.5,
        chars_processed=13,
    )

    response = client.get(f"/jobs/{job['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "done"
    assert data["duration_seconds"] == 3.5
    assert data["chars_processed"] == 13
    assert data["completed_at"] is not None


def test_get_job_failed_has_error(client):
    settings = get_settings()
    job = create_job(
        settings.sqlite_path,
        text="Will fail",
        text_hash="fail123",
        article_id=None,
        audio_url="https://audio.example.com/audio/fail123.mp3",
        backend="elevenlabs",
        voice_id="test-voice",
        webhook_url=None,
    )
    update_job_status(settings.sqlite_path, job["id"], "failed", error="synthesis error")

    response = client.get(f"/jobs/{job['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["error"] == "synthesis error"


def test_get_job_not_found_returns_404(client):
    response = client.get("/jobs/tts_nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
