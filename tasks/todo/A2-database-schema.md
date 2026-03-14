# Task: Datenbankschema + Job-CRUD
Shortcode: TTS-A2
Stage: todo
Status: ready for research
Priority: P1
Depends: A1 (config system)

---

## Definition of Done

✅ **Schema:**
- SQLite database at `config.sqlite_path` (default: `/data/jobs.db`)
- `jobs` table with all columns per ARCHITECTURE.md § 5
- All 3 indexes: `idx_jobs_text_hash`, `idx_jobs_article_id`, `idx_jobs_status`
- Migration script executes cleanly on fresh & existing databases (idempotent)

✅ **CRUD Operations** (in `app/models.py` or separate `app/db/crud.py`):
- `create_job(text, text_hash, article_id, audio_url, backend, voice_id, webhook_url)` → Job record, status=pending
- `get_job_by_id(job_id)` → Job dict or 404
- `get_job_by_text_hash(text_hash)` → Job dict or None (idempotency check)
- `get_job_by_article_id(article_id)` → Job dict or None
- `list_pending_jobs(limit=10)` → [Job] ordered by created_at ASC
- `update_job_status(job_id, new_status, completed_at=None, error=None, duration_seconds=None, chars_processed=None)` → updated record
- `update_webhook_sent(job_id, timestamp)` → mark webhook_sent_at

✅ **Models** (SQLModel or dataclass):
- Job model with all fields from ARCHITECTURE.md § 5
- Pydantic validation: `status` enum (pending|processing|done|failed)
- Timestamps: `created_at` auto-set on INSERT, `completed_at` nullable

✅ **Tests:**
- `test_create_job_inserts_correct_fields()`
- `test_get_job_by_text_hash_returns_existing()`
- `test_list_pending_jobs_respects_limit_and_order()`
- `test_update_status_sets_completed_at_on_done()`
- All CRUD operations pass with fresh DB in test suite

✅ **No external dependencies:** SQLite only, no Redis or separate service

---

## Steps

1. **Create DB module structure**
   - `app/db/` directory
   - `app/db/__init__.py`
   - `app/db/models.py` — Job model definition (SQLModel or dataclass)

2. **Define Job Model**
   - Enum for status: `pending | processing | done | failed`
   - All fields from ARCHITECTURE.md § 5 with correct types
   - Primary key: `id` (TEXT)
   - Index hints documented (not created here, see step 4)

3. **Write migrations or schema script**
   - `app/db/schema.py` — `init_db()` function that:
     - Executes CREATE TABLE IF NOT EXISTS for jobs table
     - Creates 3 indexes (idempotent — use IF NOT EXISTS)
   - Alternatively: Alembic init (if lighter approach preferred, use schema.py first)

4. **Implement CRUD layer**
   - `app/db/crud.py` — all operations listed in DoD
   - Use sqlite3 or sqlalchemy ORM (lightweight approach: sqlite3 direct)
   - All functions return dicts or None (serializable for API)

5. **Add DB initialization to app startup**
   - `app/main.py` calls `init_db()` on startup
   - Fails fast if schema cannot initialize

6. **Write tests**
   - Create `tests/test_db_models.py` or `tests/test_crud.py`
   - Fixture: temporary SQLite DB for each test
   - All CRUD operations covered (create, read, update, list)

---

## Blocking Factors

- **A1 must be done first:** Config system must be ready (config loader, path to DB file)
- **No API integration yet:** This task is DB-only. API routes come in B1/B2.
- **Storage module (A3) is independent:** Can run in parallel.

---

## Notes

- **Choice of ORM:** SQLModel or raw sqlite3 — recommend sqlite3 for simplicity (no heavy dependency)
- **Timestamps:** Use Python `datetime.now(timezone.utc).isoformat()` for consistency
- **Idempotency:** Schema creation must tolerate re-runs; use CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS
- **Text preview:** `text_preview` is optional, can be truncated to first 100 chars for debugging logs

---

## Test Coverage Checklist

- [ ] Fresh DB initializes correctly
- [ ] Job inserted with all required fields
- [ ] Text hash index prevents duplicate synthesis (query returns existing)
- [ ] Article ID index finds previous jobs (idempotency fallback)
- [ ] Status transitions: pending → processing → done
- [ ] Error state: status=failed, error message stored
- [ ] Pending jobs query respects order and limit

---

## Research & Reference

### Key Patterns

- **SQLite WAL mode:** `PRAGMA journal_mode=WAL` — erlaubt gleichzeitige Reads während ein Write läuft. Essentiell wenn API-Prozess und Worker-Prozess gleichzeitig auf die DB zugreifen. Muss einmalig beim DB-Init gesetzt werden.
- **BEGIN IMMEDIATE für atomare Schreiboperationen:** Verhindert Write-Konflikte bei mehreren Workers. `claim_next_job()` (C1) benötigt das; CRUD hier muss konsistente Transaktionen unterstützen.
- **sqlite3 vs SQLModel/SQLAlchemy:** Für diesen Scope empfohlen: reines `sqlite3` Modul. Keine schweren ORM-Dependencies, direktes SQL ist klarer und leichter testbar. SQLModel macht Sinn wenn FastAPI-Pydantic-Integration gewünscht; overhead nicht nötig für diese Größe.
- **Row factory für Dict-Returns:** `conn.row_factory = sqlite3.Row` → erlaubt `dict(row)` ohne manuelles Mapping. Alternativ: `[dict(zip(col_names, row)) for row in cursor]`.
- **check_same_thread=False:** Erforderlich wenn Connection in einem Thread erstellt wird, aber in mehreren genutzt wird. Besser: per-call Connection via Context Manager.
- **Idempotente Migration:** `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` → sicher bei re-runs und DB-Upgrades ohne Alembic-Overhead.
- **Status-Enum als TEXT:** SQLite kennt keine Enums. Status als TEXT speichern, Python-seitig als `Literal["pending", "processing", "done", "failed"]` validieren.
- **ISO-8601 Timestamps:** `datetime.now(timezone.utc).isoformat()` → konsistente UTC-Strings. SQLite speichert als TEXT, Python parst zurück mit `datetime.fromisoformat()`.

### Open Questions / Decisions

- **Connection Management:** Eine shared connection (mit Lock) oder eine new connection per call? → Empfehlung: Context Manager (`with get_db_connection() as conn:`), eine Connection pro Operation. Einfacher, kein State.
- **ORM oder kein ORM?** sqlite3 direkt ist ausreichend. Entscheidung sollte in A2 gefallen und in ARCHITECTURE.md dokumentiert sein.
- **Job-ID Format:** `tts_{uuid4()[:8]}` wie im Architektur-Doc? → Sicherstellen dass Kollisions-Wahrscheinlichkeit akzeptabel ist (~10k Jobs: vernachlässigbar). Alternativ: `tts_{uuid4()}` (voll).
- **Text speichern oder nicht?** Schema hat kein `text`-Feld — nur `text_hash` und `text_preview`. Worker braucht aber den vollen Text zum Synthetisieren. Entweder: Text mit in Job speichern (einfachster Weg), oder Consumer schickt Text mit jedem Poll (komplex). → Empfehlung: Text in Job speichern, Feld ergänzen.

### Reference Links

- [SQLite WAL mode]: https://www.sqlite.org/wal.html
- [sqlite3 Python docs]: https://docs.python.org/3/library/sqlite3.html
- [Row factory pattern]: https://docs.python.org/3/library/sqlite3.html#sqlite3.Row
- [Schema definition]: ARCHITECTURE.md §5
- [Job flow]: ARCHITECTURE.md §2 (Queue diagram)
