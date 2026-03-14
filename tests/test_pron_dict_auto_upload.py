from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import BackendsConfig, Config, ElevenLabsConfig, StorageConfig
from app.db.pronunciations import create_pronunciation
from app.db.schema import init_db
from app.worker.worker import Worker


@pytest.mark.asyncio
async def test_worker_uploads_pron_dict_and_passes_locator(tmp_path):
    db = tmp_path / "jobs.db"
    init_db(str(db))

    owner = "deadbeef" * 8

    # insert one pronunciation rule
    create_pronunciation(
        str(db),
        prn_id="prn_test",
        owner_key_hash=owner,
        language="de-DE",
        grapheme="Neckargerach",
        alias="Neckargehrach",
    )

    cfg = Config(
        default_backend="elevenlabs",
        backend_fallback_order=["elevenlabs"],
        queue={"sqlite_path": str(db)},
        storage=StorageConfig(public_base_url="http://x"),
        backends=BackendsConfig(
            elevenlabs=ElevenLabsConfig(
                enabled=True,
                api_key="eleven-key",
                default_voice="v1",
                model_id="eleven_multilingual_v2",
            ),
        ),
    )

    backend = MagicMock()
    backend.synthesize = AsyncMock(return_value=b"MP3")
    router = MagicMock()
    router.get_backend.return_value = backend

    storage = MagicMock()
    storage.write_audio.return_value = "http://x/audio.mp3"

    queue = MagicMock()
    queue.complete_job.return_value = True

    job = {
        "id": "tts_1",
        "text": "Hallo Neckargerach",
        "text_hash": "abc" * 22,
        "voice_id": "v1",
        "backend": "elevenlabs",
        "article_id": None,
        "retry_count": 0,
        "created_at": "2024-01-01T00:00:00",
        "webhook_url": None,
        "owner_key_hash": owner,
    }

    with patch("app.worker.worker.upload_dictionary_from_pls", new=AsyncMock(return_value=("dict1", "ver1"))) as up:
        worker = Worker(queue=queue, router=router, storage=storage, config=cfg)
        await worker._process_job(job)

        up.assert_awaited_once()
        # ensure locator passed
        assert backend.synthesize.await_count == 1
        kwargs = backend.synthesize.await_args.kwargs
        assert kwargs["pronunciation_dictionary_locators"] == [
            {"pronunciation_dictionary_id": "dict1", "version_id": "ver1"}
        ]


@pytest.mark.asyncio
async def test_worker_archives_old_dict_on_change(tmp_path):
    db = tmp_path / "jobs.db"
    init_db(str(db))

    owner = "deadbeef" * 8

    # initial rule
    create_pronunciation(
        str(db),
        prn_id="prn_test",
        owner_key_hash=owner,
        language="de-DE",
        grapheme="Neckargerach",
        alias="Neckargehrach",
    )

    cfg = Config(
        default_backend="elevenlabs",
        backend_fallback_order=["elevenlabs"],
        queue={"sqlite_path": str(db)},
        storage=StorageConfig(public_base_url="http://x"),
        backends=BackendsConfig(
            elevenlabs=ElevenLabsConfig(
                enabled=True,
                api_key="eleven-key",
                default_voice="v1",
                model_id="eleven_multilingual_v2",
            ),
        ),
    )

    backend = MagicMock()
    backend.synthesize = AsyncMock(return_value=b"MP3")
    router = MagicMock()
    router.get_backend.return_value = backend

    storage = MagicMock()
    storage.write_audio.return_value = "http://x/audio.mp3"

    queue = MagicMock()
    queue.complete_job.return_value = True

    job = {
        "id": "tts_1",
        "text": "Hallo Neckargerach",
        "text_hash": "abc" * 22,
        "voice_id": "v1",
        "backend": "elevenlabs",
        "article_id": None,
        "retry_count": 0,
        "created_at": "2024-01-01T00:00:00",
        "webhook_url": None,
        "owner_key_hash": owner,
    }

    # First synth uploads dict1
    with patch("app.worker.worker.upload_dictionary_from_pls", new=AsyncMock(return_value=("dict1", "ver1"))) as up1:
        with patch("app.worker.worker.archive_dictionary", new=AsyncMock()) as arch1:
            worker = Worker(queue=queue, router=router, storage=storage, config=cfg)
            await worker._process_job(job)
            up1.assert_awaited_once()
            arch1.assert_not_awaited()

    # Update rule (change hash)
    # easiest: update alias via direct SQL
    import sqlite3
    with sqlite3.connect(str(db)) as conn:
        conn.execute("UPDATE pronunciations SET alias='Neckargeeehrach' WHERE id='prn_test'")

    # Second synth uploads dict2 and archives dict1
    with patch("app.worker.worker.upload_dictionary_from_pls", new=AsyncMock(return_value=("dict2", "ver2"))) as up2:
        with patch("app.worker.worker.archive_dictionary", new=AsyncMock()) as arch2:
            worker = Worker(queue=queue, router=router, storage=storage, config=cfg)
            await worker._process_job(job)
            up2.assert_awaited_once()
            arch2.assert_awaited_once()
            args = arch2.await_args.kwargs
            assert args["dictionary_id"] == "dict1"
