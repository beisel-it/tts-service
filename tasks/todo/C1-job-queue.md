# Task: Job-Queue API (SQLite polling interface)
**Shortcode:** TTS-C1  
**Stage:** todo  
**Status:** ready for research  
**Priority:** P1

## Description
Implementiere die Queue-Abstraktionsschicht als Python-Modul `app/worker/queue.py`. Dieses Modul exponiert die Job-Management-Operationen für den Worker-Loop (C2): Job aus Queue holen, Status aktualisieren (pending → processing → done/failed), Fehlerbehandlung mit Retry-Zähler.

**Kontext:**
- Zielbackend: SQLite (jobs.db, bestehend aus TTS-A2)
- Polling-Stil: Worker fragt alle N Sekunden nach pending Jobs
- Atomarität: `claim_next_job()` muss Race Conditions verhindern (SELECT + UPDATE in einer Transaktion)
- Idempotenz: Rücksicht auf article_id-Deduplication (architecture §3.4, §5)

## Definition of Done

### 1. claim_next_job()
- ✅ SELECT mit WHERE status='pending' ORDER by created_at ASC LIMIT 1
- ✅ UPDATE desselben Rows: status='processing', beginne Zeitmessung
- ✅ Atomare Transaktion mit BEGIN IMMEDIATE (verhindert Doppel-Pickup bei parallelen Workers)
- ✅ Gibt Job-Dict zurück: {id, text, text_hash, voice_id, backend, article_id, retry_count, created_at}
- ✅ Gibt None zurück wenn queue leer
- ✅ Testbar: Unit-Test mit Mock-DB, zwei parallele claim-Aufrufe → nur einer kriegt denselben Job

### 2. complete_job(job_id, duration_seconds, **kwargs)
- ✅ UPDATE status='done', completed_at=NOW, duration_seconds setzen
- ✅ kwargs: {audio_url, storage_key, chars_processed} optional setzen falls vorhanden
- ✅ Atomare Transaktion
- ✅ Returniert True bei Erfolg, Raises JobNotFoundError wenn job_id nicht existiert
- ✅ Testbar: Job wird auf status='done' geprüft, Timestamps sind SET und konsistent

### 3. fail_job(job_id, error_msg, force_permanent=False)
- ✅ Wenn force_permanent=False (default): increment retry_count, status bleibt 'pending' (rückt für nächsten Poll in die Queue zurück)
- ✅ Wenn force_permanent=True ODER retry_count >= 3: status='failed', error_msg setzen, completed_at=NOW
- ✅ Atomare Transaktion
- ✅ Returniert (success: bool, retry_count_after: int)
- ✅ Testbar: fail mit force_permanent=False → Job hat retry_count+1; fail nach 3 Versuchen → status='failed'

### 4. get_job_status(job_id)
- ✅ SELECT job record, return status + metadata {status, audio_url, error, retry_count, completed_at}
- ✅ Für Polling/Monitoring use-case
- ✅ Testbar: Status passt zum aktuellen DB-Zustand

### 5. Logging & Observability
- ✅ Strukturiertes Logging (JSON oder Key=Value format) für claim/complete/fail
- ✅ Logs enthalten: timestamp, job_id, action, retry_count, error (falls relevant)
- ✅ Log-Level: DEBUG für claim, INFO für complete, WARN für fail, ERROR für force_permanent
- ✅ Ready für späteren Export zu Monitoring/Alerting

## Implementation Steps

1. **Queue-Klasse schreiben:** `class Queue:` mit SQLite connection (configurable path), pooling oder context manager
2. **claim_next_job() mit atomarer Transaktion:** `BEGIN IMMEDIATE; SELECT...; UPDATE status=processing; COMMIT`
3. **complete_job() + fail_job():** Status-Transition-Logik, Timestamp-Handling, Retry-Counter Management
4. **get_job_status():** Read-only query für Monitoring
5. **Custom Exceptions:** JobNotFoundError, QueueError (für externe Fehlerbehandlung sauber)
6. **Tests schreiben:** 4-5 Unit Tests (claim atomic, complete updates, fail with retries, status query, concurrent claim)
7. **Docstrings + Type Hints:** Jede Methode mit Args/Returns/Raises, Python 3.10+ type annotations

## Blocking Factors / Notes
- **Depends on:** TTS-A2 (jobs.db Schema muss existieren, Indizes auf status + created_at)
- **No external service calls** — reine DB-Logik, selbstständig testbar
- **SQLite Pragmas:** queue.py sollte on initialization setzen: `PRAGMA journal_mode=WAL;` ← für Multiprocess-Sicherheit
- **Context Manager:** Queue-Klasse sollte optional as-context-manager benutzbar sein (`with Queue(...) as q:`)

## Acceptance Criteria for Testing & Handoff

1. ✅ `pytest tests/test_queue.py::test_claim_atomic` — keine Doppel-Pickup bei Parallelität
2. ✅ `pytest tests/test_queue.py::test_complete_job` — status + timestamps korrekt  
3. ✅ `pytest tests/test_queue.py::test_fail_retry` — Retry-Zähler inkrementiert bis max
4. ✅ `pytest tests/test_queue.py::test_fail_permanent` — status=failed nach retries oder force
5. ✅ Queue-Modul importierbar ohne Fehler: `from app.worker.queue import Queue`
6. ✅ Methode-Signaturen passen zu C2-Consumer (Worker-Loop braucht diese exakte API)
7. ✅ Keine SQL-Injection (alle Parameter are bound/parameterized)
8. ✅ Logging funktioniert, ist konfigurierbar (DEBUG/INFO/WARN/ERROR Levels)

---

**Ready für Research/Code-Phase:** Code-Implementierung, pytest, Fehlerbehandlung, Integration in C2

---

## Research & Reference

### Key Patterns

- **`BEGIN IMMEDIATE` für atomares Claim:** Das Kernmuster für SQLite-basierte Queues mit mehreren Consumern. `BEGIN IMMEDIATE` sperrt die DB für Writes sofort (nicht erst beim ersten Write-Statement). Ablauf: `BEGIN IMMEDIATE → SELECT pending LIMIT 1 → UPDATE status=processing → COMMIT`. Kein zweiter Worker kann denselben Job greifen solange diese Transaktion läuft.
- **WAL-Mode Pflicht:** `PRAGMA journal_mode=WAL` muss bei DB-Init gesetzt sein (A2). WAL erlaubt gleichzeitige Reads (API-Prozess) während Queue-Writes laufen. Ohne WAL: Lesende Prozesse blockieren auf Write-Lock.
- **`PRAGMA busy_timeout=5000`:** Wenn SQLite-Lock nicht sofort verfügbar ist (z.B. zwei Workers starten gleichzeitig), wartet SQLite bis 5 Sekunden bevor OperationalError geworfen wird. Verhindert sofortiges Crash bei kurzen Locks.
- **Connection Context Manager:** `with sqlite3.connect(db_path) as conn:` — auto-commit auf success, auto-rollback auf Exception. Für jede Operation neue Connection (oder Connection-Pool mit Lock).
- **Queue als Klasse mit `__enter__`/`__exit__`:** Erlaubt `with Queue(config) as q: q.claim_next_job()`. Clean API für C2.
- **Retry-Logik im fail_job:** `retry_count` in der DB tracken. `fail_job(force_permanent=False)`: wenn `retry_count + 1 >= max_retries (3)` → `status='failed'`. Sonst: `status='pending'`, `retry_count++`. Job taucht beim nächsten Poll wieder auf.

### Open Questions / Decisions

- **`text` Feld im Job-Record:** `claim_next_job()` muss den vollen Text zurückgeben damit der Worker synthetisieren kann. Wenn Text nicht im Schema ist (vgl. A2 Open Question) → muss dort ergänzt werden. C1 blockiert auf diese Entscheidung.
- **Polling-Interval:** Konfigurierbar in config.yaml (`worker.polling_interval_seconds`, default 2s). C1 selbst wartet nicht — die Wartezeit liegt im Worker-Loop (C2). C1 ist reine DB-Logik.
- **Mehrere Worker-Instanzen:** `BEGIN IMMEDIATE` + WAL ist ausreichend für 2-3 Worker-Instanzen auf einem Server. Für mehr: Redis oder Postgres Queue. Nicht relevant für MVP.
- **Job-Ordering:** FIFO (ORDER BY created_at ASC) ist das richtige Default. Kein Priority-System für MVP.

### Reference Links

- [SQLite BEGIN IMMEDIATE]: https://www.sqlite.org/lang_transaction.html
- [SQLite WAL]: https://www.sqlite.org/wal.html
- [SQLite Queue Pattern]: https://www.sqlite.org/appfileformat.html (general patterns)
- [busy_timeout pragma]: https://www.sqlite.org/pragma.html#pragma_busy_timeout
- [Job schema]: ARCHITECTURE.md §5
- [Queue in Architecture]: ARCHITECTURE.md §2
- [C2 Worker Loop]: C2-worker-loop.md (Consumer dieser API)
