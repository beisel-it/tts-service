# Task: Fallback Backend — Retry with Alternative Backends
**Shortcode:** TTS-E2  
**Stage:** todo  
**Status:** todo  
**Priority:** P2

## Description
Implementiere Fallback-Logik im Worker (C2) und optional in der API (B1), die bei Fehlern von einem Backend zu einem alternativen Backend wechselt. Dies erhöht die Verfügbarkeit — wenn ElevenLabs gerade Rate-Limited ist oder offline, können wir auf Azure/Polly ausweichen. Der Fallback ist konfigurierbar und loggt alle Versuche strukturiert.

**Kontext:**
- Fallback-Kette in Config definiert: `backend_fallback_order: ["elevenlabs", "azure", "polly"]`
- Worker versucht erstes Backend; bei recoverable-error (Rate Limit, Timeout, Network): nächstes in der Kette
- Non-recoverable errors (Auth-Fehler): kein Fallback, direkt failed
- Jeder Fallback-Versuch wird geloggt + gezählt (für Monitoring)
- Webhook und API-Response zeigen `backend_used` — welches Backend hat schlussendlich geklappt

## Definition of Done

### 1. Fallback-Konfiguration
- ✅ Config erweitert um `backend_fallback_order: List[str]` — Reihenfolge für Fallback versuche
- ✅ Standardwert fallback_order: `["elevenlabs", "azure", "polly"]`
- ✅ Konfigurierbar pro Job (optional im Request-Body) oder global

### 2. Error-Klassifizierung im Worker
- ✅ Definiere error types (in router.py oder backends/base.py):
  - **Recoverable:** `NetworkError`, `TimeoutError`, `RateLimitError`, `TemporaryServiceError`
  - **Non-Recoverable:** `AuthenticationError`, `InvalidVoiceError`, `InvalidTextError`
- ✅ Jede Backend-Implementierung (D1, Azure, Polly) throwt passende Exception-Typen
- ✅ Exception-Hierarchie: `TTSError` (base) → Recoverable/NonRecoverable subclasses

### 3. Worker Fallback-Loop (C2 erweitern)
- ✅ Worker hält aktuell `primary_backend` von Config/Request
- ✅ Neu: `fallback_order: List[str]` laden aus `config.backend_fallback_order`
- ✅ Fallback-Loop:
  ```python
  for backend_name in fallback_order:
      try:
          backend = router.get_backend(backend_name)
          audio_bytes = await backend.synthesize(...)
          job.backend_used = backend_name
          break  # Erfolg
      except RecoverableError as e:
          log.warn(f"Backend {backend_name} failed (recoverable), trying next...", error=e)
          continue
      except NonRecoverableError as e:
          log.error(f"Backend {backend_name} failed (non-recoverable)", error=e)
          fail_job(job_id, force_permanent=True)
          return
  else:
      # Alle Backends versucht, alle fehlgeschlagen
      log.error(f"All backends in fallback_order failed for job {job_id}")
      fail_job(job_id, force_permanent=True)
  ```

### 4. Job-Tracking
- ✅ Job-DB erweitert:
  - `backend_used: str` — welches Backend hat geklappt
  - `backends_tried: List[str]` — Json-Array aller versuchten Backends [optional, für Audit]
  - `retry_backends: int` — Anzahl Fallback-Versuche die gemacht wurden
- ✅ Nach erfolgreicher Synth: `update_job(job_id, backend_used=backend_name, status="done")`
- ✅ Webhook + API-Response zeigen `backend_used`

### 5. Logging & Monitoring
- ✅ Jeder Fallback-Versuch geloggt:
  - `log.warn("Fallback: trying alternative backend", current_backend=X, next_backend=Y, error=reason)`
  - Strukturiert mit: job_id, backend_tried, attempt_number, error_type, error_message
- ✅ Erfolgreicher Fallback geloggt:
  - `log.info("Fallback successful", job_id=..., original_backend=X, final_backend=Y)`
- ✅ Alle Backends fehlgeschlagen:
  - `log.error("All backends exhausted", job_id=..., backends_tried=[...], error=reason)`

### 6. API Response (B1 erweitern)
- ✅ Job-Status Response zeigt `backend_used` und evtl. `backends_tried`:
  ```json
  {
    "job_id": "...",
    "status": "done",
    "backend_used": "azure",  // welches Backend hat geklappt
    "backends_tried": ["elevenlabs", "azure"],  // optional, für debugging
    "audio_url": "...",
    ...
  }
  ```

### 7. Non-Recoverable Error Handling
- ✅ Wenn NonRecoverableError (z.B. auth error): sofort `fail_job(force_permanent=True)`
- ✅ Kein Fallback für Auth-Fehler — Problem ist strukturell, nicht transient
- ✅ InvalidVoiceError, InvalidTextError: auch non-recoverable (Config/Input-Fehler)

### 8. Testing Support
- ✅ Mock-Backends für Tests die gezielt Errors werfen:
  - `MockFailingBackend(error_type="RateLimitError")` → worft RecoverableError
  - `MockAuthFailBackend()` → wirft NonRecoverableError
- ✅ Fallback-Chain Test: 3 Backends, erster 2 fail recoverable, dritter succeeds

### 9. Configuration Validation
- ✅ Bei Startup: Prüfe ob alle Backends in `fallback_order` konfiguriert sind
- ✅ Fallback-Länge: Mindestens 1 Backend, maximal 4 (sinnvolle Grenze)

## Implementation Steps

1. **Exception-Hierarchie erweitern:**
   - `TTSError(Exception)` (base)
   - `RecoverableError(TTSError)` → Network, Timeout, RateLimit, Temporary
   - `NonRecoverableError(TTSError)` → Auth, InvalidVoice, InvalidText
   - Konkrete Subclasses: `NetworkError`, `RateLimitError`, `AuthenticationError`, etc.

2. **Config erweitern:**
   - `config.backend_fallback_order: List[str]` laden
   - Default: `["elevenlabs", "azure", "polly"]`
   - Validation: alle names sind registered backends

3. **Worker-Loop (C2) erweitern:**
   - Load `fallback_order` aus Config
   - Fallback-Loop um synthesize() call bauen
   - Recoverable → continue to next, NonRecoverable → fail permanent
   - Job.backend_used aktualisieren

4. **Job-DB Schema erweitern:**
   - `ALTER TABLE jobs ADD COLUMN backend_used TEXT`
   - `ALTER TABLE jobs ADD COLUMN backends_tried TEXT` (JSON array, optional)
   - `ALTER TABLE jobs ADD COLUMN retry_backends INTEGER DEFAULT 0`

5. **Backends aktualisieren (D1, D2, D3 + Stubs):**
   - ElevenLabs: RateLimitError für 429, NetworkError für Connection-Fehler
   - Azure/Polly Stubs: auch richtige Exceptions werfen
   - Jedes Backend throwt konkrete Exception-Typen

6. **Unit-Tests schreiben:**
   - `test_fallback_to_second_backend` — erster Backend-Error (recoverable), zweiter succeeds
   - `test_all_backends_fail` — alle Backends in Kette werfen Recoverable → final fail_job
   - `test_nonfatal_error_no_fallback` — NonRecoverableError → sofort fail, kein fallback
   - `test_fallback_logging` — Log entries für jeden Versuch
   - `test_api_response_shows_backend_used` — Response enthält `backend_used`

7. **API-Response (B1) aktualisieren:**
   - Job.backend_used in Response JSON serialisieren
   - backends_tried optional hinzufügen (falls geloggt)

8. **Monitoring-Metrik vorbereiten:**
   - Log-Format so strukturiert, dass später Metriken aggregiert werden können
   - Beispiel: `log.info("backend_event", job_id=..., event_type="fallback", backend=X)`

## Blocking Factors / Dependencies
- **Depends on:**
  - TTS-E1 (Backend Router muss existieren + InvalidBackendError werfen)
  - TTS-D1+ (Backends müssen Exceptions werfen können)
  - TTS-C2 (Worker-Loop muss diese Fallback-Logik integrieren)
  - TTS-A1 (Config System muss backend_fallback_order laden)
  - TTS-A2 (Job-Schema muss backend_used + retry_backends Felder haben)
- **Blockiert durch:**
  - Erfordert dass mindestens 2 Backends implementiert sind (für sinnvolle Fallback-Tests)
- **Integration:**
  - Wird in C2 Worker-Loop integriert
  - Wirkt sich auf Logging + Monitoring aus

## Acceptance Criteria for Testing & Handoff

1. ✅ `pytest tests/test_fallback.py::test_fallback_first_backend_fails` — Erster Backend 429 → Fallback → Zweiter succeeds
2. ✅ `pytest tests/test_fallback.py::test_nonfatal_error_skips_fallback` — InvalidVoiceError → fail_permanent, kein fallback
3. ✅ `pytest tests/test_fallback.py::test_all_backends_exhausted` — Alle 3 Backends fail → job status=failed
4. ✅ `pytest tests/test_fallback.py::test_fallback_logging_structured` — Log entries enthalten backend_name, error_type, attempt
5. ✅ `pytest tests/test_fallback.py::test_custom_fallback_order` — Fallback-Reihenfolge kann konfiguriert werden
6. ✅ Worker startet: `python -m app.worker.worker` — fallback_order geladen, keine Errors
7. ✅ API Response: GET /jobs/{id} zeigt `backend_used` Feld (string)
8. ✅ Database: `backend_used` Spalte existiert + wird gefüllt
9. ✅ Config validation: Startup-Fehler wenn fallback_order Backend enthält, das nicht konfiguriert ist
10. ✅ Fallback-Limit: maximal 4 Backends in Fallback-Kette erlaubt

---

**Ready für Code-Phase:** Fallback-Loop Implementierung, Exception-Hierarchie, Worker-Integration, Tests und API-Response-Anpassung

## Notes for Implementation
- Fallback logic sollte idempotent sein — wenn Worker nach Synthesize crasht, retry startet wieder bei Primary-Backend (nicht wo es abbrach)
- Für Multi-Worker-Setups: Kein shared state nötig, jeder Worker hat eigene Fallback-Logik
- Rate-Limit-Awareness: Wenn Backend A 429 wirft, nicht sofort probieren (vielleicht nach 60s), aber für diese Task: einfach fallback machen
