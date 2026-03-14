"""Worker loop — continuously processes TTS jobs from the queue.

See Tasks C2 (Worker-Loop) and E2 (Fallback-Logik) for the specification.

The worker:
  1. Claims the next pending job from the SQLite queue (C1).
  2. Tries each backend in the fallback order (E2).
  3. Writes the audio to local storage (A3).
  4. Marks the job done/failed in the queue.
  5. Handles SIGTERM/SIGINT gracefully (finishes current job, then exits).
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time
from typing import TYPE_CHECKING

from app.backends.base import NonRecoverableError, RecoverableError
from app.backends.router import BackendRouter, InvalidBackendError
from app.config import Config, load_config
from app.storage.local import LocalStorage
from app.worker.queue import JobDict, JobNotFoundError, Queue
from app.db.pron_dict_state import get_state, upsert_state
from app.db.pronunciations import list_pronunciations
from app.pronunciation.elevenlabs_sync import upload_dictionary_from_pls
from app.pronunciation.pls import build_pls, pls_hash

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def _ensure_pronunciation_locator_for_job(*, config: Config, job: dict) -> list[dict[str, str]]:
    """Return pronunciation_dictionary_locators for this job (per-consumer), or [] if none."""

    owner = job.get("owner_key_hash")
    if not owner:
        return []

    # only supported for ElevenLabs backend
    eleven_cfg = config.backends.elevenlabs
    if not eleven_cfg.enabled or not eleven_cfg.api_key:
        return []

    # Load pronunciation rules for this consumer
    language = "de-DE"
    rules = list_pronunciations(config.queue.sqlite_path, owner_key_hash=owner, language=language)
    if not rules:
        return []

    pls = build_pls(language=language, items=rules)
    h = pls_hash(pls)

    state = get_state(config.queue.sqlite_path, owner_key_hash=owner)
    if state is not None and state.last_pls_hash == h:
        return [{"pronunciation_dictionary_id": state.dictionary_id, "version_id": state.version_id}]

    # Upload dictionary snapshot (non-spammy: only when synth occurs)
    name = f"tts-service-{owner[:8]}"
    description = "tts-service consumer pronunciation overrides"
    dict_id, ver_id = await upload_dictionary_from_pls(
        api_key=eleven_cfg.api_key,
        name=name,
        description=description,
        pls_content=pls,
    )

    upsert_state(
        config.queue.sqlite_path,
        owner_key_hash=owner,
        dictionary_id=dict_id,
        version_id=ver_id,
        last_pls_hash=h,
    )

    return [{"pronunciation_dictionary_id": dict_id, "version_id": ver_id}]



class Worker:
    """Processes TTS jobs from the queue in a polling loop.

    Args:
        queue: Queue instance for job management.
        router: BackendRouter for backend selection and lazy init.
        storage: LocalStorage for writing audio files.
        config: Application configuration.
    """

    def __init__(
        self,
        queue: Queue,
        router: BackendRouter,
        storage: LocalStorage,
        config: Config,
    ) -> None:
        self._queue = queue
        self._router = router
        self._storage = storage
        self._config = config
        self._shutdown_requested = False

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def request_shutdown(self) -> None:
        """Signal the worker to stop after the current job completes."""
        logger.info("Shutdown requested — will stop after current job")
        self._shutdown_requested = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Run the polling loop until shutdown is requested."""
        interval = self._config.worker.polling_interval_seconds
        fallback_order = self._config.backend_fallback_order or [self._config.default_backend]

        logger.info(
            "Worker started polling_interval=%.1fs max_retries=%d fallback_order=%s",
            interval,
            self._config.worker.max_retries,
            fallback_order,
        )

        while not self._shutdown_requested:
            job = self._queue.claim_next_job()
            if job is None:
                logger.debug("Queue empty, sleeping %.1fs", interval)
                await asyncio.sleep(interval)
                continue

            await self._process_job(job)

        logger.info("Worker stopped (shutdown requested)")

    # ------------------------------------------------------------------
    # Job processing
    # ------------------------------------------------------------------

    async def _process_job(self, job: JobDict) -> None:
        """Process a single job through the fallback backend chain.

        Implements the E2 fallback loop:
          - RecoverableError  → try next backend in fallback_order
          - NonRecoverableError → fail job permanently (no fallback)
          - All backends exhausted → fail job (retryable unless max retries hit)
        """
        job_id: str = job["id"]
        text: str = job["text"]
        voice_id: str = job.get("voice_id") or ""
        webhook_url: str | None = job.get("webhook_url")
        text_hash: str = job.get("text_hash") or ""
        retry_count: int = job.get("retry_count", 0)

        logger.info(
            "Processing job job_id=%s text_length=%d voice_id=%s retry_count=%d",
            job_id,
            len(text),
            voice_id,
            retry_count,
        )

        start = time.monotonic()

        # --- E2: Fallback loop ---
        fallback_order = self._config.backend_fallback_order or [self._config.default_backend]
        audio_bytes: bytes | None = None
        backend_used: str | None = None
        backends_tried: list[str] = []
        last_error: Exception | None = None

        for backend_name in fallback_order:
            backends_tried.append(backend_name)

            # Resolve backend instance
            try:
                backend = self._router.get_backend(backend_name)
            except (InvalidBackendError, Exception) as exc:
                logger.warning(
                    "Fallback: backend '%s' unavailable job_id=%s error=%s",
                    backend_name, job_id, exc,
                )
                last_error = exc
                continue

            # Attempt synthesis
            try:
                logger.debug(
                    "Attempting backend='%s' job_id=%s", backend_name, job_id
                )
                audio_bytes = await asyncio.wait_for(
                    backend.synthesize(
                        text=text,
                        voice_id=voice_id,
                        **({"pronunciation_dictionary_locators": await _ensure_pronunciation_locator_for_job(config=self._config, job=job)} if backend_name == "elevenlabs" else {}),
                    ),
                    timeout=self._config.worker.synthesize_timeout_seconds,
                )
                backend_used = backend_name
                logger.info(
                    "Backend succeeded backend='%s' job_id=%s bytes=%d",
                    backend_name, job_id, len(audio_bytes),
                )
                if len(backends_tried) > 1:
                    logger.info(
                        "Fallback successful job_id=%s original_backend=%s final_backend=%s",
                        job_id, backends_tried[0], backend_name,
                    )
                break  # success

            except NonRecoverableError as exc:
                logger.error(
                    "Non-recoverable error backend='%s' job_id=%s error=%s",
                    backend_name, job_id, exc,
                )
                self._queue.fail_job(
                    job_id,
                    str(exc),
                    force_permanent=True,
                    backends_tried=backends_tried,
                )
                return

            except (RecoverableError, asyncio.TimeoutError, OSError) as exc:
                logger.warning(
                    "Fallback: backend='%s' failed (recoverable) job_id=%s error=%s — trying next",
                    backend_name, job_id, exc,
                )
                last_error = exc
                continue

        if audio_bytes is None:
            # All backends exhausted
            error_msg = str(last_error) if last_error else "All backends exhausted"
            logger.error(
                "All backends exhausted job_id=%s backends_tried=%s error=%s",
                job_id, backends_tried, error_msg,
            )
            self._queue.fail_job(
                job_id,
                f"All backends failed: {error_msg}",
                force_permanent=False,
                backends_tried=backends_tried,
            )
            return

        # --- Write to storage ---
        try:
            audio_url = self._storage.write_audio(audio_bytes, text_hash)
            storage_key = f"{text_hash[:8]}/{text_hash}.mp3"
        except Exception as exc:
            logger.error(
                "Storage write failed job_id=%s error=%s", job_id, exc
            )
            self._queue.fail_job(
                job_id,
                f"Storage error: {exc}",
                force_permanent=True,
                backends_tried=backends_tried,
            )
            return

        duration = time.monotonic() - start

        # --- Complete job ---
        try:
            self._queue.complete_job(
                job_id,
                duration_seconds=duration,
                audio_url=audio_url,
                storage_key=storage_key,
                chars_processed=len(text),
                backend_used=backend_used,
                backends_tried=backends_tried,
            )
        except JobNotFoundError as exc:
            logger.error("complete_job: job not found job_id=%s: %s", job_id, exc)
            return

        logger.info(
            "Job complete job_id=%s backend=%s duration=%.2fs",
            job_id, backend_used, duration,
        )

        # --- Webhook dispatch (C3 stub) ---
        if webhook_url:
            asyncio.create_task(
                self._dispatch_webhook(job_id, audio_url, webhook_url)
            )

    async def _dispatch_webhook(
        self, job_id: str, audio_url: str, webhook_url: str
    ) -> None:
        """Fire-and-forget webhook notification (full implementation in C3)."""
        logger.info(
            "Webhook dispatch job_id=%s webhook_url=%s audio_url=%s",
            job_id, webhook_url, audio_url,
        )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


async def worker_main(config: Config | None = None) -> None:
    """Async entrypoint: load config, wire up dependencies, run worker."""
    cfg = config or load_config()

    queue = Queue(cfg.queue.sqlite_path, max_retries=cfg.worker.max_retries)
    router = BackendRouter(cfg)
    storage = LocalStorage(cfg.storage)

    worker = Worker(queue=queue, router=router, storage=storage, config=cfg)

    # Register SIGTERM/SIGINT for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_shutdown)

    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(worker_main())
        sys.exit(0)
    except Exception as exc:
        logger.error("Worker crashed: %s", exc)
        sys.exit(1)
