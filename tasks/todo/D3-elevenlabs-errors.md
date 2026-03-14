# Task: ElevenLabs Error-Handling + Retry
Shortcode: TTS-D3
Stage: todo
Status: ready for research
Priority: P2

## Summary
Implement robust error-handling and retry logic for ElevenLabs backend. Define custom exceptions for each failure mode (rate limit, auth, network) and apply exponential backoff with jitter for transient failures. Must integrate cleanly with Worker's job failure semantics.

## Definition of Done (testable criteria)
- ✅ Custom exceptions in `app/backends/elevenlabs.py`:
  - `ElevenLabsAuthError` (401/403) — permanent, fail job immediately
  - `ElevenLabsRateLimitError` (429) — transient, obey Retry-After header
  - `ElevenLabsAPIError` (5xx, 4xx non-auth) — transient, exponential backoff
  - `ElevenLabsNetworkError` (connection timeout, DNS fail) — transient, exponential backoff
- ✅ Retry policy:
  - Auth failures: 0 retries (immediate fail)
  - Rate limit (429): 1 retry after `Retry-After` header (default 60s)
  - Other API errors (5xx): up to 3 retries with exponential backoff (1s, 2s, 4s)
  - Network errors: up to 3 retries with exponential backoff (0.5s, 1s, 2s)
- ✅ Exponential backoff formula: `base * (2 ^ attempt) + jitter(0, 1s)`
- ✅ Rate limit detection: parse `x-ratelimit-remaining` and `Retry-After` from response headers
- ✅ Logging: each retry attempt and final failure reason logged at WARNING level
- ✅ Worker integration: `Job.error` field captures exception message + type for debugging
- ✅ Test coverage: 
  - Unit tests for each exception type + retry logic
  - Integration test: mock 429 response, verify retry + eventual success
  - Integration test: mock 401, verify immediate fail
  - Integration test: mock network timeout, verify backoff sequence

## Implementation Steps
1. Define exception classes in `app/backends/elevenlabs.py` (inherit from base `TTSBackendError`)
2. Implement retry decorator or context manager in `app/backends/elevenlabs.py`:
   - Accept max_retries, base_delay, jitter_range
   - Handle each exception type according to policy
   - Log each attempt (attempt #N, waiting Xs, reason)
3. Wrap `synthesize()` call in retry logic in `ElevenLabsBackend.synthesize()`
4. Wrap `list_voices()` call in retry logic in `ElevenLabsBackend.list_voices()`
5. Update Worker to catch exceptions + set `job.error` + transition to `failed` state
6. Add comprehensive tests in `tests/test_elevenlabs_backend.py`:
   - Mock 429 → Retry-After header → verify retry + success
   - Mock 401 → immediate fail, no retry
   - Mock connection timeout → verify exponential backoff sequence
   - Mock random network error → verify up to 3 retries

## Blocking Factors
- Depends on TTS-D1 (ElevenLabsBackend base class)
- Depends on Worker implementation (Job model + error field) — can be stubbed with `try/except` for now

## Notes
- ElevenLabs API errors reference: https://elevenlabs.io/docs/api-reference/errors
- Retry-After header format: seconds (integer) or HTTP date
- Jitter prevents thundering herd (all retries happening at same time)
- Rate limit headers typically: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`
- Keep error messages user-friendly for end consumer (e.g., "Service temporarily unavailable, retrying...")
- All logging should go to standard logger + be structured (name, level, exception type)

---

## Research & Reference

### Key Patterns

- **Exception Hierarchy:** Basis `TTSBackendError(Exception)` in `base.py`. Davon abgeleitet in `elevenlabs.py`: `ElevenLabsAuthError`, `ElevenLabsRateLimitError(retry_after: int)`, `ElevenLabsAPIError`, `ElevenLabsNetworkError`. Worker fängt `TTSBackendError` generisch, kann aber spezifisch auf `ElevenLabsRateLimitError` prüfen.
- **`Retry-After` Header parsen:** ElevenLabs gibt bei 429 `Retry-After: 60` (Sekunden als Integer) oder HTTP-Date zurück. `int(response.headers.get("Retry-After", 60))` — safe default 60s wenn Header fehlt.
- **Jitter gegen Thundering Herd:** `delay = base_delay * (2 ** attempt) + random.uniform(0, 1)`. Bei mehreren Workers die gleichzeitig 429 kriegen, verhindert Jitter synchronisierten Retry-Burst.
- **tenacity Library:** Professionelles Retry-Framework. `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=30), retry=retry_if_exception_type(ElevenLabsNetworkError))`. Eleganter als manuelles Try/Except + Sleep. Dependency: `tenacity`.
- **httpx Timeout → NetworkError:** `except httpx.TimeoutException as e: raise ElevenLabsNetworkError(str(e)) from e`. Alle httpx-Exceptions (ConnectError, ReadTimeout, etc.) zu `ElevenLabsNetworkError` wrappen.
- **Auth-Fehler nicht retrien:** `ElevenLabsAuthError` hat `retryable = False`. Worker-Logik: wenn `not error.retryable` → `fail_job(force_permanent=True)`. Retrybare Errors: `force_permanent=False`.

### Open Questions / Decisions

- **tenacity oder manuell?** tenacity ist gut gepflegt und macht Tests einfacher (mocker). Manuelle Retry-Loop ist transparenter aber mehr Code. → Empfehlung: tenacity für D3. Dependency ist minimal.
- **Retry innerhalb Backend oder im Worker?** Zwei Ebenen möglich: Backend retried intern (transparent für Worker), Worker retried extern (via Queue). → Empfehlung: Netzwerkfehler im Backend retrien (intern, schnell). Rate-Limit im Worker retrien (via Queue + Backoff-Sleep), weil 60s Wartezeit die Worker-Loop nicht blockieren soll.
- **Rate-Limit als permanent-fail oder retry-via-queue?** Bei 429 soll Worker nicht 60 Sekunden schlafen und die Loop blockieren. Besser: `fail_job(force_permanent=False)` + im Worker vor dem nächsten Claim `min(Retry-After, 60)` Sekunden warten. Worker kann dann andere Jobs prozessieren... aber bei Single-Backend gibt es keine anderen. → Für MVP: `asyncio.sleep(retry_after)` im Worker nach RateLimitError akzeptabel, da Volumen gering.

### Reference Links

- [ElevenLabs Error Codes]: https://elevenlabs.io/docs/api-reference/errors
- [tenacity docs]: https://tenacity.readthedocs.io/
- [httpx Exception types]: https://www.python-httpx.org/exceptions/
- [Retry-After RFC]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
- [C2 Worker fail_job]: C2-worker-loop.md §5 (Retry Logic)
