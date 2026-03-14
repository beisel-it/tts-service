# Task: API-Key Auth Middleware
Shortcode: TTS-B4
Stage: refinement
Status: refined
Priority: P1

## Dependencies
- **A1:** Config system (config.service.api_key must be loaded)
- FastAPI dependency system (available in any FastAPI project setup)

## Definition of Done

### Middleware Function
Scope: **Protect all endpoints except /health**

Request flow:
```
1. Request arrives with header X-API-Key
2. Middleware checks: header value == config.service.api_key?
3. YES → Allow request, attach to request context
4. NO → Return 401 Unauthorized
5. SPECIAL CASE: GET /health → Skip auth, allow through
```

### Response Specification

**Success (valid API key):**
- No response change, request proceeds to endpoint handler

**Failure (missing/invalid key):**
```
401 Unauthorized
Content-Type: application/json

{
  "detail": "Invalid or missing API key"
}
```

Criteria:
- [x] Extracts X-API-Key header from incoming request
- [x] Compares against `config.service.api_key` (loaded from environment or config.yaml)
- [x] Returns 401 if missing or doesn't match
- [x] **Explicitly exempts** `GET /health` from auth check
- [x] Applies to **all other endpoints** (/synthesize, /jobs/{id}, /admin/voices)
- [x] Error response includes `detail` field with clear message
- [x] Uses FastAPI Depends() pattern (dependency injection)

## Implementation Steps

1. **Create `app/middleware/auth.py`** (new file):
   - Import: HTTPException, status, Request, Depends from fastapi
   - Import: settings/config module
   - Define async function `verify_api_key(request: Request)`:
     - Extract X-API-Key header
     - Compare to config.service.api_key
     - If missing/invalid: raise HTTPException(status_code=401, detail="Invalid or missing API key")
     - If valid: return key (or True)

2. **Register middleware in `app/main.py`**:
   - Import auth.py module
   - Define a check function that returns True if path == "/health" (skip auth)
   - Apply middleware to FastAPI instance using `@app.middleware("http")` OR use route-level dependencies
   - Recommended: route-level via `Depends(verify_api_key)` on individual endpoints that need it

3. **Route-level application** (cleaner than global middleware):
   - Apply `Depends(verify_api_key)` to:
     - `POST /synthesize`
     - `GET /jobs/{id}`
     - `GET /admin/voices`
   - **DO NOT apply** to `GET /health`

4. **Configuration**:
   - Ensure `config.service.api_key` is set (from environment var `TTS_SERVICE_API_KEY` or config.yaml)
   - Validate at app startup: if api_key is empty/None, log warning but allow (for dev mode) or raise error (for prod)

## Blocking & Risk

- **Blocker:** A1 (Config system) not ready → can't load service.api_key
- **Risk:** Hardcoded/empty key in dev environment → security issue if deployed to prod
- **Risk:** API key visible in logs if not careful → ensure it's not logged in debug output

## Testing Strategy
- Unit: Mock config, call verify_api_key() with valid/invalid/missing keys → assert 401 on failure
- Integration:
  - Start app with TTS_SERVICE_API_KEY="test-key"
  - GET /health → 200 (no auth required)
  - POST /synthesize without key → 401
  - POST /synthesize with correct key → proceeds (or 400 if payload invalid, but not 401)
  - POST /synthesize with wrong key → 401

## Scope Boundaries
- **In Scope:**
  - Header extraction and comparison
  - 401 response format
  - Exemption logic for /health
  - Dependency injection into protected endpoints
- **NOT in Scope:**
  - Key rotation or expiration (static key for now, per ARCHITECTURE.md)
  - Rate limiting (different concern, separate task if needed)
  - Logging of auth failures (keep minimal, don't leak keys)

## Security Notes
- API key is simple string comparison — sufficient for internal service, not for public API
- Exempting /health is intentional (load balancers and container orchestration need public health checks)
- All other endpoints are protected equally
- If key is empty in prod, that's a deployment error, not an auth bypass

## Integration with B3
- B3 (admin/voices) depends on B4 for protection
- B3 /health endpoint explicitly bypasses B4 auth
- After B4 is done, B3 can be implemented knowing auth is handled

---

## Research & Reference

### Key Patterns

- **FastAPI `Depends()` statt globaler Middleware:** Route-Level Dependency Injection ist sauberer als `@app.middleware("http")` für diesen Use-Case. Jede protected Route bekommt `Depends(verify_api_key)`. `/health` bekommt es nicht. Kein globales Path-Matching nötig.
- **`APIKeyHeader` aus fastapi.security:** `from fastapi.security import APIKeyHeader` → `api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)`. `auto_error=False` → manuelle Kontrolle über den 401-Response statt FastAPI-Default.
- **Timing-Safe Comparison:** `hmac.compare_digest(provided_key, expected_key)` statt `==` — verhindert Timing-Angriffe (theoretisch). Bei internem Service über HTTPS: overkill aber kostet nichts.
- **Leerer Key in Dev:** Config-Validation beim Start: wenn `api_key` leer ist und `ENV != development` → Startup-Error. Dev-Mode erlaubt leeren Key mit WARN-Log.
- **Dependency Signature:** `async def verify_api_key(api_key: str = Security(api_key_header)) -> str:` — returns key on success, raises HTTPException(401) on failure.

### Open Questions / Decisions

- **`APIKeyHeader` vs Custom Header Extraction:** `APIKeyHeader` macht automatisch OpenAPI-Dokumentation für den Header. Empfohlen gegenüber manuellem `Request.headers.get("X-API-Key")`.
- **Key in Logs:** Sicherstellen dass `api_key` nie in Logs landet — weder als Variable-Dump noch im Exception-Traceback. Pydantic Settings: `api_key: SecretStr` (verhindert repr-Ausgabe).
- **Mehrere Keys / Key Rotation:** Out of scope für MVP. Wenn gewünscht: Config-Array `api_keys: list[str]`, prüfen ob provided in list. Bis dahin: single static key.

### Reference Links

- [FastAPI Security - API Key Header]: https://fastapi.tiangolo.com/tutorial/security/api-key/
- [fastapi.security.APIKeyHeader]: https://fastapi.tiangolo.com/reference/security/#fastapi.security.APIKeyHeader
- [Pydantic SecretStr]: https://docs.pydantic.dev/latest/concepts/types/#secret-types
- [hmac.compare_digest]: https://docs.python.org/3/library/hmac.html#hmac.compare_digest
- [Config]: ARCHITECTURE.md §7 (service.api_key)
