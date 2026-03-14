# Task: GET /health + GET /admin/voices
Shortcode: TTS-B3
Stage: refinement
Status: refined
Priority: P3

## Dependencies
- **A1:** Config system (service.api_key, default_backend, backends config)
- **A2:** Database schema + Jobs CRUD (jobs table, query queue_depth)
- **D2:** Backend interface + list_voices() implementation
- **B4:** API-Key Auth Middleware (B3 endpoints ARE guarded, except /health is special)

## Definition of Done

### Endpoint: GET /health
Scope: **No authentication** (public healthcheck for load balancers)

```
200 OK
{
  "status": "ok",
  "database": "ok",      // SQLite connectivity check, "error" if unavailable
  "queue_depth": 5,      // COUNT(*) FROM jobs WHERE status IN ('pending', 'processing')
  "uptime_seconds": 3600
}
```

Criteria:
- [x] Returns 200 with structure above
- [x] DB connection check: try query, catch exception → status="ok" if connected, db="error" if not
- [x] Queue depth: query jobs table, returns 0 if no pending jobs
- [x] Uptime calculated from app startup timestamp (track at module init)
- [x] **NO authentication required** (explicit exemption from B4 middleware)

### Endpoint: GET /admin/voices
Scope: **API-Key authenticated**, lists available voices from currently configured backend

```
200 OK
{
  "backend": "elevenlabs",
  "voices": [
    {"id": "XB0fDUnXU5powFXDhCwa", "name": "Charlotte", "language": "de-DE"},
    {"id": "...", "name": "...", "language": "..."}
  ]
}
```

Criteria:
- [x] Calls configured backend's `list_voices()` method (backend selection via config)
- [x] Returns backend name (active backend) + voice list with id/name/language fields
- [x] Handles backend call failure (network error, API quota, auth failure) → 503 Service Unavailable with error_message field
- [x] **API-Key guarded**: 401 Unauthorized if X-API-Key missing/invalid (enforced by B4 middleware)

## Implementation Steps

1. **Create `app/api/routes_admin.py`** (new file):
   - Import: FastAPI, HTTPException, database models, backend router
   - Define async `check_health()`: timestamp app startup, query jobs table for queue_depth, calculate uptime
   - Define async `list_voices()`: call backend.list_voices(), return structured response
   - Register both endpoints in router

2. **Register routes in `app/main.py`**:
   - Import routes_admin module
   - Include router in FastAPI app (no auth dependency on /health, auth dependency on /admin/voices via B4)

3. **Health check implementation details**:
   - Store app startup time as module-level variable at app init
   - DB check: execute simple COUNT query on jobs table
   - If DB unreachable: catch exception, return db="error"
   - Queue depth: SELECT COUNT(*) FROM jobs WHERE status IN ('pending', 'processing')

4. **Voices endpoint implementation details**:
   - Get current backend from BackendRouter (or config default)
   - Call backend.list_voices() (must be async)
   - Return with backend name + voice list
   - If backend call fails: catch exception, return 503 with error detail

## Blocking & Risk

- **Blocker:** B4 not ready → can scaffold auth param, integration test blocked
- **Blocker:** A2 (database) not initialized → health check fails on DB query
- **Blocker:** Backend.list_voices() interface not finalized → assume `list[VoiceInfo]` per ARCHITECTURE.md §4
- **Risk:** Queue depth query on hot table might slow load balancer checks → consider caching health state for 5–10s

## Testing Strategy
- Unit: Mock database, mock backend → test response structure
- Integration: Bring up A1+A2+D1 (ElevenLabs), call endpoints, verify structure
- Production: Monitor load balancer hitting /health every N seconds, verify no errors

## Notes
- /health is deliberately public (no auth) — used by Docker health checks & external load balancers
- /admin/voices is admin-only — scoped for internal voice management/debugging
- Queue depth updates in real-time (no caching)

---

## Research & Reference

### Key Patterns

- **Health Check Standards:** `/health` ist de-facto Standard für Docker HEALTHCHECK und Kubernetes liveness probes. Response-Body mit `{"status": "ok"}` ist ausreichend — komplexere Standards (readyz/livez Split) erst wenn Kubernetes-Deploy geplant.
- **Startup-Zeitstempel für Uptime:** `APP_START_TIME = datetime.now(timezone.utc)` als Modul-Level Variable in `app/main.py` beim Start. `uptime_seconds = (datetime.now(timezone.utc) - APP_START_TIME).total_seconds()`.
- **DB-Check ohne Overhead:** `SELECT 1` auf der Jobs-DB reicht. Kein COUNT, kein Table-Scan. Exception → `"database": "error"`. Health-Check sollte nie mehr als ~5ms dauern.
- **Voice-List Caching:** `list_voices()` macht einen externen API-Call (ElevenLabs). Nicht bei jedem `/admin/voices`-Request wiederholen. TTL-Cache: `functools.lru_cache` reicht nicht (kein Timeout). Besser: `cachetools.TTLCache(maxsize=1, ttl=300)` — 5 Minuten Refresh. Dependency: `cachetools`.
- **503 bei Backend-Fehler:** `/admin/voices` schlägt Backend-API → `raise HTTPException(503, detail=str(e))`. Consumer weiss: Service läuft, aber Backend gerade nicht erreichbar.

### Open Questions / Decisions

- **Queue-Depth im Health-Check:** `SELECT COUNT(*) FROM jobs WHERE status IN ('pending', 'processing')` — könnte bei sehr hohem Traffic minimal verlangsamen. Bei diesem Volumen: kein Problem. WAL-Mode erlaubt Read ohne Write-Lock.
- **Voice-Cache invalidieren:** Wenn Voice-Config sich ändert (neuer voice_id), ist Cache 5 Minuten outdated. Akzeptabel für Admin-Endpoint.
- **`/admin/voices` Auth-Exemption für Monitoring?** → Nein, bleibt Auth-geschützt. Nur `/health` ist public.

### Reference Links

- [Health check patterns]: https://microservices.io/patterns/observability/health-check-api.html
- [Docker HEALTHCHECK]: https://docs.docker.com/engine/reference/builder/#healthcheck
- [cachetools TTLCache]: https://cachetools.readthedocs.io/en/stable/#cachetools.TTLCache
- [FastAPI dependencies]: https://fastapi.tiangolo.com/tutorial/dependencies/
- [Auth integration]: B4 Task (verify_api_key dependency)
