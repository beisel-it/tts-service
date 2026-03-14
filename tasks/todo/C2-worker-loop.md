# Task: Worker-Loop (Job processing with graceful shutdown)
**Shortcode:** TTS-C2  
**Stage:** todo  
**Status:** ready for research  
**Priority:** P1

## Description
Implementiere die Worker-Schleife als Python-Prozess (`app/worker/worker.py`), der kontinuierlich Jobs aus der Queue abholt, an das konfigurierte TTS-Backend delegiert, die Ausgabe in Storage schreibt und Job-Status aktualisiert. Der Worker handhabt Fehler mit exponentialem Backoff (bis max 3 Versuche), sauberes Shutdown bei SIGTERM, und Webhook-Triggering nach Completion.

**Kontext:**
- Worker läuft als Background-Prozess, konfigurierbar horizontal skalierbar (N=1..3 Instanzen)
- Abhängigkeit: Queue (C1) für Job-Management, Backend-Interface (D1+ für TTS-Aufrufe, Storage (A3) für Audio-Dateien
- Synchrone Polling-Loop: `while True: claim → process → complete/fail` mit konfigurierbarem Polling-Interval (default 2 Sekunden)
- Webhook-Dispatch (C3) integriert nach successfull completion

## Definition of Done

### 1. Worker-Loop Initialization
- ✅ Entrypoint: `if __name__ == "__main__": worker_main()` lädt config, initialisiert Queue + Backend Router
- ✅ Signal Handler für SIGTERM + SIGINT registrieren → `graceful_shutdown()` flag setzen
- ✅ Logging initialisieren (strukturiert, JSON oder Key=Value, Level aus config)
- ✅ Testbar: `python -m app.worker.worker` startet ohne Errors, antwortet auf Signal + Shutdown

### 2. Main Polling Loop
- ✅ Polling-Interval konfigurierbar (default: 2 Sekunden, aus config geladen)
- ✅ `claim_next_job()` aufrufen → wenn None, sleep(interval) + continue
- ✅ Bei Job: `log.info("Processing job", job_id=...)`
- ✅ Backend aus Job.backend auswählen via Router (bei error: fail_job mit `force_permanent=False`)
- ✅ Timeout pro Synthesize-Aufruf: 60 Sekunden (konfigurierbar, z.B. je Backend anders)
- ✅ Graceful Shutdown: nach aktuellem Job fertig sein, nicht mitten in Synthesize abbrechen

### 3. Backend Integration
- ✅ `backend.synthesize(text=job.text, voice_id=job.voice_id) → bytes` aufrufen
- ✅ Exception Handling: `ElevenLabsError`, `TimeoutError`, `RuntimeError` → fail_job mit retry
- ✅ Special Case: Rate-Limit (429) → exponential backoff, retry sofort (nicht warten, nur fail_job + backend router gibt Hint)
- ✅ On Success: audio_bytes erhalten, übergeben an Storage

### 4. Storage Integration
- ✅ `storage.write(audio_bytes, text_hash=job.text_hash, content_type="audio/mpeg") → storage_key` aufrufen
- ✅ Error Handling: Schreibfehler → fail_job mit `force_permanent=True` (nicht retry-bar, Storage ist OS-Problem)
- ✅ Auf Success: `complete_job(job_id, duration_seconds=job_elapsed, audio_url=..., storage_key=...)`

### 5. Retry Logic & Exponential Backoff
- ✅ Initiale Versuche: max 3 (konfigurierbar via config.worker.max_retries)
- ✅ Zwischen Retry-Versuchen: backoff = min(2^retry_count * initial_delay, max_delay). Initial=1s, Max=30s
- ✅ fail_job() handhabt: retry_count >= max_retries → `force_permanent=True`, sonst retry-ready
- ✅ Testbar: Simuliere flüchtige Fehler (z.B. ConnectionError) → Job wird 3× versucht, dann failed

### 6. Webhook Dispatch
- ✅ Nach complete_job: Wenn job.webhook_url gesetzt, trigger `webhook_dispatcher.send(job_id, job_url, callback_url)`
- ✅ Webhook-Dispatcher läuft async/background (nicht blocking auf Worker-Loop)
- ✅ Logging: Webhook-Aufruf Log, Success/Failure
- ✅ Testbar: Job mit webhook_url → Complete Job → Webhook wird enqueued/sent

### 7. Logging & Monitoring
- ✅ Strukturiertes Logging mit Key=Value oder JSON: job_id, backend, text_length, duration_ms, retry_attempt, success/error
- ✅ Log-Levels: DEBUG (claim), INFO (start/complete), WARN (retry), ERROR (permanent fail)
- ✅ Metrics (optional für Phase 1, aber Strukturvorbereitung): elapsed_ms, chars_per_second, backend_success_rate
- ✅ Testbar: Log-Ausgabe parsen, erwartete Keys vorhanden

### 8. Graceful Shutdown
- ✅ SIGTERM Handler setzt Flag `shutdown_requested = True`
- ✅ Laufender Job wird zu Ende bracht (nicht abgebrochen)
- ✅ Nach Completion: Loop-Bedingung prüft `shutdown_requested`, bricht aus Loop
- ✅ Cleanup: Queue-Verbindung schließen, Logging flushen
- ✅ Exit-Code: 0 (clean) oder 1 (error)
- ✅ Testbar: `docker stop <container>` → Worker beendet sich sauber innerhalb von X Sekunden

## Implementation Steps

1. **Worker-Klasse schreiben:** `class Worker:` mit __init__(queue, backend_router, storage, config, logger)
2. **Main polling loop:** `while not shutdown_requested: ...` mit claim/process/complete cycle
3. **Backend-Aufrufe:** Try-except um `backend.synthesize()`, delegiere zu fail_job mit retry logic
4. **Storage-Integration:** audio_bytes → storage.write(), error-handling mit force_permanent
5. **Webhook-Integration:** Nach complete_job, trigger async dispatcher (delegiere zu C3)
6. **Signal Handlers:** SIGTERM/SIGINT → set shutdown_requested flag, allow current job to finish
7. **Retry Logic:** Exponential backoff in fail_job Logik (Queue wertet das aus, Worker ruft nur fail_job auf)
8. **Tests schreiben:** 5-6 Integration Tests (happy path, retry on transient error, graceful shutdown, webhook trigger, storage error handling)
9. **Docstrings + Type Hints:** Worker-Klasse + main loop documented
10. **Entrypoint:** `if __name__ == "__main__": worker_main()` konfiguriert alles + startet Worker

## Blocking Factors / Notes
- **Depends on:**
  - TTS-C1 (Queue API muss existieren + working)
  - TTS-A3 (Storage API: write() mit Return-Value)
  - TTS-D1 (ElevenLabs Backend, mindestens ein Backend muss implementiert sein)
  - TTS-A1 (Config System, damit polling_interval_seconds + max_retries geladen werden)
- **No sync external calls blocking loop** — Storage write ist sync, aber kurz (< 1s erwartet)
- **Signal Handling:** Python signal module, works on Unix/Linux + macOS, Windows behavior may differ (akzeptabel)
- **Graceful Shutdown Implementation:** atexit + signal handlers, nicht hardcoded timeouts

## Acceptance Criteria for Testing & Handoff

1. ✅ `pytest tests/test_worker.py::test_happy_path` — Job lädt → synthesize → storage → complete → status=done
2. ✅ `pytest tests/test_worker.py::test_retry_transient_error` — Fehler 2× → dann success → status=done (retry hat geklappt)
3. ✅ `pytest tests/test_worker.py::test_permanent_fail_after_max_retries` — 3 Fehlversuche → status=failed
4. ✅ `pytest tests/test_worker.py::test_graceful_shutdown` — SIGTERM während Job → Job wird zu Ende gebracht, dann exit
5. ✅ `pytest tests/test_worker.py::test_webhook_dispatch` — Nach complete_job + webhook_url → webhook dispatcher triggered
6. ✅ `pytest tests/test_worker.py::test_storage_write_error_permanent_fail` — Storage.write() Error → fail_job(force_permanent=True)
7. ✅ Worker-Modul startbar: `python -m app.worker.worker` → keine ImportErrors
8. ✅ Konfigurierbar: config.yaml Werte (polling_interval_seconds, max_retries, backend, voice_id) werden geladen + angewendet
9. ✅ Logging strukturiert, keine unerwarteten Exceptions im Log
10. ✅ Shutdown-Verhalten beobachtbar: Nach SIGTERM, aktuelle Job endet, dann Exit (< 5 Sekunden)

---

**Ready für Research/Code-Phase:** Worker-Implementierung, Error Handling, Integration Tests, Docker entrypoint config

---

## Research & Reference

### Key Patterns

- **Signal Handling in Python:** `signal.signal(signal.SIGTERM, handler)` — Handler setzt `shutdown_requested = True` (threading.Event oder einfache Bool). Wichtig: Handler darf kein I/O machen. Loop prüft das Flag nach jedem Job. SIGINT (Ctrl+C) gleich behandeln. `signal.signal(signal.SIGINT, handler)`.
- **Exponential Backoff Formel:** `delay = min(base_delay * (2 ** retry_count), max_delay)`. Default: `base_delay=1s`, `max_delay=30s`. Retry 0 → 1s, Retry 1 → 2s, Retry 2 → 4s. Max 3 Retries → dann `fail_job(force_permanent=True)`. Worker wartet NICHT selbst — er ruft `fail_job(force_permanent=False)` auf und der Job taucht nach dem nächsten Poll wieder auf. Backoff ist optional: Sleep vor dem nächsten Poll-Cycle.
- **Synchroner Worker mit asyncio für Backend-Calls:** ElevenLabs-Backend ist async (httpx). Worker-Entrypoint: `asyncio.run(worker_main())`. Polling-Loop: `async def run_loop()`. `await backend.synthesize(...)`. Kein Threading nötig.
- **Graceful Shutdown Sequence:** SIGTERM → `shutdown_requested = True` → aktueller Job läuft zu Ende → `await queue.release()` → `sys.exit(0)`. Docker stop sendet SIGTERM, wartet default 10s, dann SIGKILL. Sicherstellen dass ein Job in <10s fertig wird (ElevenLabs: typisch 3-7s).
- **Timer für Job-Dauer:** `start = time.monotonic()` vor `backend.synthesize()`, `elapsed = time.monotonic() - start` danach. An `complete_job(duration_seconds=elapsed)` übergeben.
- **Storage-Fehler als permanent:** Wenn `storage.write()` wirft, ist das kein transienter Fehler (Disk voll, Permission). → `fail_job(force_permanent=True)`. Nicht retrien.
- **Asyncio Timeout:** `asyncio.wait_for(backend.synthesize(...), timeout=60)` — ElevenLabs-Call mit Timeout absichern. TimeoutError → transient fail → retry.

### Open Questions / Decisions

- **Asyncio oder Threading?** → Asyncio empfohlen, da ElevenLabs-Backend eh async (httpx). Einfacher als Threading mit Locks.
- **Mehrere Worker-Instanzen:** Einfachste Form: `docker-compose scale worker=3`. Jede Instanz ein eigener Prozess, eigene Event-Loop. SQLite BEGIN IMMEDIATE handhabt die Konkurrenz.
- **Rate-Limit Handling:** ElevenLabs 429 → `Retry-After` Header auswerten, diesen Wert als Sleep nutzen vor dem Retry. Nicht blind exponential backoff. D3 Task implementiert das im Backend — C2 bekommt `ElevenLabsRateLimitError` mit `retry_after_seconds` Attribut.
- **Worker Health:** Wie sieht der API-Prozess ob der Worker noch läuft? → Für MVP: `/health` zeigt `queue_depth` — wenn Jobs pending und nicht processing werden, ist der Worker tot. Kein separater Worker-Healthcheck.

### Reference Links

- [Python signal handling]: https://docs.python.org/3/library/signal.html
- [asyncio.run()]: https://docs.python.org/3/library/asyncio-runner.html
- [asyncio.wait_for() timeout]: https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for
- [Exponential backoff]: https://cloud.google.com/storage/docs/retry-strategy#exponential-backoff
- [Docker graceful shutdown]: https://docs.docker.com/engine/reference/commandline/stop/ (SIGTERM + grace period)
- [C1 Queue API]: C1-job-queue.md (claim_next_job, complete_job, fail_job)
- [A3 Storage API]: A3-local-storage.md (write_audio)
- [D1 Backend Interface]: ARCHITECTURE.md §4
- [C3 Webhook]: C3-webhook-dispatcher.md
