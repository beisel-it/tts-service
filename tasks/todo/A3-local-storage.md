# Task: Lokales Storage-Modul + Cleanup
Shortcode: TTS-A3
Stage: todo
Status: ready for research
Priority: P1
Depends: A1 (config system)

---

## Definition of Done

✅ **File Storage**
- Module: `app/storage/local.py`
- Function `write_audio(audio_bytes: bytes, text_hash: str) -> str`
  - Creates `/data/audio/{hash[:8]}/` directory (with parents)
  - Writes bytes to `/data/audio/{hash[:8]}/{hash}.mp3`
  - Returns public URL: `{config.storage.public_base_url}/audio/{hash[:8]}/{hash}.mp3`
  - Idempotent: re-writing same hash doesn't fail, overwrites cleanly

✅ **URL Generation**
- `get_audio_url(text_hash: str) -> str`
  - Combines `config.storage.public_base_url` + hash-based path
  - No file existence check (URL is promised at job creation time)

✅ **Cleanup Function**
- `cleanup_old_files(days: int = 7)`
  - Walks `/data/audio/` directory tree
  - Checks file modification time: if older than `now() - timedelta(days=days)`, delete
  - Logs deletions (info level)
  - Non-destructive: errors on single file don't block rest of cleanup
  - Returns count of deleted files

✅ **Storage Initialization**
- `init_storage()`
  - Creates `/data/audio/` directory if missing
  - Validates write permissions
  - Called by `app/main.py` on startup

✅ **Configuration**
- Read from `config.storage.path` (default: `/data/audio`)
- Read from `config.storage.public_base_url` (e.g., `https://tts.service/audio`)
- Read from `config.storage.cleanup_after_days` (default: 7)

✅ **Tests:**
- `test_write_audio_creates_subdirectory()`
- `test_write_audio_returns_correct_url()`
- `test_get_audio_url_matches_written_file()`
- `test_cleanup_old_files_removes_files_older_than_threshold()`
- `test_cleanup_respects_recent_files()`
- `test_init_storage_creates_directory()`

✅ **No external storage service:** Local filesystem only.

---

## Steps

1. **Create storage module structure**
   - `app/storage/` directory
   - `app/storage/__init__.py`
   - `app/storage/local.py` — all functions

2. **Implement file write and URL generation**
   - `write_audio(audio_bytes, text_hash)`:
     - Parse config for `storage.path`
     - Create subdirectory: `pathlib.Path(path).mkdir(parents=True, exist_ok=True)`
     - Write file atomically (write to temp file, then rename — optional but safer)
     - Return URL combining config `public_base_url` + hash path
   - `get_audio_url(text_hash)`:
     - Simply construct URL from config + hash, no I/O

3. **Implement cleanup function**
   - `cleanup_old_files(days=7)`:
     - Walk storage directory
     - For each file: check `mtime`, compare to `now() - timedelta(days=days)`
     - Delete if older, catch exceptions per file
     - Log deletions and count
   - Handle edge cases: empty dirs, permission errors

4. **Implement storage initialization**
   - `init_storage()`:
     - Get path from config
     - Create directory with `mkdir(parents=True, exist_ok=True)`
     - Test write permission (create temp file, delete it)
     - Log success or raise on failure

5. **Add to app startup**
   - `app/main.py` calls `init_storage()` before starting API
   - Logs initialization success
   - Fails fast if storage cannot be initialized

6. **Nginx config snippet**
   - Document (in comment or separate file) the Nginx location config:
     ```nginx
     location /audio/ {
         alias /data/audio/;
         expires 30d;
         add_header Cache-Control "public, immutable";
     }
     ```
   - Note: This is documentation only; actual Nginx setup is in G3 (Deployment task)

7. **Write tests**
   - Create `tests/test_storage_local.py`
   - Fixture: temporary directory as storage root
   - Cover all functions, including cleanup edge cases

---

## Blocking Factors

- **A1 must be done first:** Config system must provide `storage` section
- **No worker integration yet:** Worker writes to storage in E1
- **Nginx config is separate task:** G3 handles deployment; this is just documentation

---

## Notes

- **Directory structure:** `{path}/{hash[:8]}/{full_hash}.mp3` allows sharding (future optimization for large file counts)
- **Atomic writes:** Optional—use `tempfile` + `rename` if concerned about partial writes; direct write is fine for MVP
- **Cleanup timing:** Can be triggered by worker on each job completion, or via cron. For MVP, assume worker or manual trigger.
- **Permissions:** Ensure directory owner is app user (non-root), not root. Deployment task handles this.
- **Logging:** Use Python `logging` module, not print. Level: INFO for successful writes, DEBUG for cleanup details.

---

## Test Coverage Checklist

- [ ] Directory created on first write
- [ ] File written to correct nested path
- [ ] Public URL format matches expected pattern
- [ ] Multiple writes to same hash overwrite cleanly
- [ ] Cleanup query identifies old files correctly (mtime-based)
- [ ] Cleanup skips recent files
- [ ] Cleanup handles permission errors gracefully
- [ ] Storage init creates directory
- [ ] Storage init detects write permission
- [ ] Storage init fails fast on permission denied

---

## Research & Reference

### Key Patterns

- **Hash-basiertes Sharding:** `/data/audio/{hash[:8]}/{hash}.mp3` — identisch zum Git Object Store Prinzip. Die ersten 8 Chars als Subdirectory limitieren Directory-Einträge auf ~256 Verzeichnisse mit je maximal N Files. Bei diesem Volumen (380k Z/Monat ≈ wenige hundert Files/Monat) ist das over-engineering, aber schadet nicht und skaliert.
- **pathlib statt os.path:** `Path(base) / hash[:8] / f"{hash}.mp3"` — lesbar, plattformunabhängig, `.mkdir(parents=True, exist_ok=True)` für sicheres Verzeichnis-Anlegen.
- **Atomic writes:** `tmp = path.with_suffix('.tmp')` → `tmp.write_bytes(data)` → `tmp.rename(path)`. Rename ist atomar auf POSIX-Systemen (gleiche Partition). Verhindert halbfertige Files wenn der Prozess während des Schreibens stirbt.
- **mtime für Cleanup:** `path.stat().st_mtime` → `datetime.fromtimestamp(mtime)`. Einfachster Weg. Alternative: `st_atime` (last access) — aber unreliable wenn noatime mount option gesetzt ist. mtime ist sicherer.
- **Promise URL:** `get_audio_url(text_hash)` berechnet die URL rein aus String-Concat, kein I/O. URL ist also deterministisch und sofort verfügbar — das ist der Kernmechanismus des Promise-URL-Modells (ARCHITECTURE.md §1).
- **pathlib.rglob('*.mp3'):** Für Cleanup. Elegant, kein os.walk nötig. `for f in Path(base).rglob('*.mp3'): ...`

### Open Questions / Decisions

- **Atomic write: notwendig für MVP?** Wenn Worker crashed, bleibt eine kaputte .tmp Datei liegen. cleanup_old_files könnte *.tmp mitlöschen. → Empfehlung: atomic write implementieren, ist 2 Zeilen mehr und das richtige Default.
- **Cleanup-Trigger:** Periodisch via Worker (z.B. jede N-te Iteration) oder separater Cron? → MVP: Worker ruft cleanup einmal pro Stunde auf (Counter-basiert in der Loop). Kein separater Prozess nötig.
- **Leere Subdirectories löschen?** Nach Cleanup können leere `{hash[:8]}/` Dirs zurückbleiben. → `dir.rmdir()` nach File-Delete wenn dir leer — optional, Kosmetik.
- **Write-Permissions testen:** `init_storage()` soll Permissions prüfen — Temp-File anlegen und löschen ist die zuverlässigste Methode vs. reiner `os.access()` Check.

### Reference Links

- [pathlib Python docs]: https://docs.python.org/3/library/pathlib.html
- [Git object storage inspiration]: https://git-scm.com/book/en/v2/Git-Internals-Git-Objects
- [POSIX atomic rename]: https://rcrowley.org/2010/01/06/things-unix-can-do-atomically.html
- [Storage config]: ARCHITECTURE.md §6
- [URL format]: ARCHITECTURE.md §6 (Dateinamen-Schema)
- [Nginx serving config]: ARCHITECTURE.md §6 (Auslieferung) + G3 Task
