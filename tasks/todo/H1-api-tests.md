# Task: API-Tests (pytest + httpx)
Shortcode: TTS-H1
Stage: todo
Status: ready for research
Priority: P2

## Definition of Done

### Test Coverage (TestClient + httpx)
- [ ] Test file: `tests/test_api.py` with 3 test classes
- [ ] All endpoints tested: `/synthesize`, `/jobs/{id}`, `/health`, `/admin/voices`
- [ ] Auth middleware validated (X-API-Key header)
- [ ] Input validation (422 for bad requests)
- [ ] Idempotency verified (201 on new, 200 on duplicate text_hash)

### POST /synthesize Test Cases
- [ ] **201 Created** on new valid request (voice, backend, text, article_id optional)
- [ ] **201** response includes: `job_id`, `status: "pending"`, `audio_url`, `poll_url`, `estimated_seconds`
- [ ] **200 Cached** on duplicate text_hash (same text, different request) → returns existing job
- [ ] **200 Cached** on duplicate article_id (same article already synthesized) → returns existing job
- [ ] **401 Unauthorized** when X-API-Key missing or invalid
- [ ] **422 Unprocessable Entity** when text is empty or > 10000 chars
- [ ] **422** when backend is invalid or voice_id doesn't exist for backend
- [ ] Webhook URL validation (if provided)

### GET /jobs/{id} Test Cases
- [ ] **200 OK** when job exists with status "done" → includes `audio_url`, `duration_seconds`, `chars_processed`, `backend_used`
- [ ] **200 OK** when job exists with status "pending" → includes `job_id`, `status`, `created_at`, no `completed_at`
- [ ] **200 OK** when job exists with status "failed" → includes `error` reason
- [ ] **404 Not Found** when job_id doesn't exist
- [ ] **401 Unauthorized** when X-API-Key missing

### GET /health Test Cases
- [ ] **200 OK** with `{"status": "healthy", "version": "..."}` or minimal payload
- [ ] No authentication required (public endpoint)

### GET /admin/voices Test Cases
- [ ] **200 OK** returns array of available voices per backend
- [ ] Response format: `[{backend: "elevenlabs", voices: [{voice_id, name, language, ...}]}]`
- [ ] **401 Unauthorized** if X-API-Key required for this endpoint (check spec)

## Implementation Steps
1. Create `tests/test_api.py` with pytest fixtures (test app, TestClient)
2. Implement `test_synthesize_new()` — POST with new text → 201
3. Implement `test_synthesize_cached_hash()` — same text → 200 + cached flag
4. Implement `test_synthesize_cached_article()` — same article_id → 200 + cached flag
5. Implement `test_synthesize_no_auth()` → 401
6. Implement `test_synthesize_bad_input()` → 422 (empty, too long, bad backend)
7. Implement `test_synthesize_webhook_validation()` — valid/invalid webhook URLs
8. Implement `test_get_job_done()` → 200 with full details
9. Implement `test_get_job_pending()` → 200 without completed_at
10. Implement `test_get_job_failed()` → 200 with error text
11. Implement `test_get_job_not_found()` → 404
12. Implement `test_get_job_no_auth()` → 401
13. Implement `test_health()` → 200 public
14. Implement `test_admin_voices()` → 200 or 401 (check spec)
15. Run: `pytest tests/test_api.py -v --cov=app.api`

## Blocking Issues
- [ ] **Clarify:** Is GET /admin/voices auth-required? Check spec or ask requester.
- [ ] **Clarify:** What is max text length? Spec says 10000 — confirm.
- [ ] **Clarify:** Should 200 Cached response include `cached: true` flag? (Best practice: yes)

## Notes
- Use `@pytest.fixture(scope="function")` for TestClient (fresh state per test)
- Mock the worker queue and backend calls (don't hit real APIs)
- Test response schemas match spec exactly (use Pydantic validation)
- Idempotency tests are critical — text_hash deduplication is core feature

## Depends On
- TTS-B1 (POST /synthesize endpoint)
- TTS-B2 (GET /jobs/{id} endpoint)
- TTS-B3 (GET /health + /admin/voices)
- TTS-B4 (API-Key auth middleware)

---

## Research & Reference

### Key Patterns

- **FastAPI TestClient:** `from fastapi.testclient import TestClient; client = TestClient(app)` — synchrones Interface über `httpx`, kein laufender Server nötig. Für async Endpoints: TestClient handled das intern. Fixtures: `@pytest.fixture def client(): return TestClient(app)`.
- **In-Memory SQLite für Tests:** `":memory:"` als DB-Pfad in der Test-Config. Jeder Test bekommt eine frische DB via Fixture: `@pytest.fixture(autouse=True) def fresh_db(): init_db(":memory:"); yield; close_db()`. Alternativ: `tmp_path` Fixture von pytest für File-basierte Temp-DB (besser für Tests die Persistence prüfen).
- **Dependency Override für Mocks:** `app.dependency_overrides[get_db] = lambda: test_db` — FastAPI-natives Pattern um Dependencies (DB, Queue, Backend) in Tests durch Mocks zu ersetzen. Kein Monkey-Patching nötig.
- **Idempotenz testen:** Zwei Requests mit identischem `text` senden → erster Response: `status=201, cached=false` → zweiter Response: `status=200, cached=true`, gleiche `job_id` und `audio_url`. Das ist der Core-Feature-Test.
- **Mocking des Worker-Backends:** Tests für `/synthesize` sollen keine echten TTS-Calls machen. Queue + Backend via `dependency_overrides` oder `unittest.mock.patch` mocken. Job wird in Queue gestellt aber nie prozessiert — Status bleibt `pending`. Für Tests die `done`-Status brauchen: Job direkt in DB auf `done` setzen.
- **Parametrize für Edge Cases:** `@pytest.mark.parametrize("text,expected", [("", 422), ("x" * 5001, 422), ("valid", 201)])` — sauber für Input-Validation-Tests.

### Open Questions / Decisions

- **Max text length:** DoD sagt 10000, aber ElevenLabs-Limit ist 5000 (aus D1-Research). → Klären bevor Tests geschrieben werden. Test mit 5001 Zeichen muss 422 ergeben.
- **`/admin/voices` Auth-required?** B3-Task sagt ja. H1-DoD fragt. → Antwort: Ja, auth-required (laut B3-Spec). Test: ohne Key → 401.
- **`cached`-Flag im Response:** Architecture-Doc §3.4 beschreibt `cached: true` im Response. Tests müssen dieses Feld prüfen. Sicherstellen dass B1 das wirklich zurückgibt.
- **`estimated_seconds` im Response:** Wie berechnet? Tests können `estimated_seconds >= 0` prüfen ohne exact value.

### Reference Links

- [FastAPI TestClient]: https://fastapi.tiangolo.com/tutorial/testing/
- [FastAPI Dependency Override]: https://fastapi.tiangolo.com/advanced/testing-dependencies/
- [pytest tmp_path fixture]: https://docs.pytest.org/en/stable/how-to/tmp_path.html
- [pytest parametrize]: https://docs.pytest.org/en/stable/how-to/parametrize.html
- [API Spec]: ARCHITECTURE.md §3 (alle Endpoints + Response-Schemas)
- [Idempotency Spec]: ARCHITECTURE.md §3.4
- [Auth Spec]: B4-auth-middleware.md
