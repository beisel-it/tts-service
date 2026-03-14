# Task: ElevenLabs Backend-Tests (respx mock)
Shortcode: TTS-H2
Stage: todo
Status: ready for research
Priority: P2

## Definition of Done

### Mock Framework & Setup
- [ ] Use `respx` for HTTP mocking (preferred over httpretty for httpx)
- [ ] Test file: `tests/test_elevenlabs_backend.py`
- [ ] Fixtures: `elevenlabs_backend` instance, `mock_api` respx router
- [ ] No real API calls — all requests mocked

### synthesize() Method Test Cases
- [ ] **200 OK** → returns bytes (valid MP3 audio data)
  - Mock: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
  - Verify: correct voice_id, text in body, model_id in payload
  - Assert: returned bytes are not empty, content looks like MP3 header
- [ ] **429 Too Many Requests** → Retry with exponential backoff
  - Mock: First request returns 429 + Retry-After header
  - Second request returns 200 + audio bytes
  - Assert: synthesize() eventually succeeds (or max retries exceeded)
  - Assert: delays between retries are correct (exponential: 1s, 2s, 4s...)
- [ ] **401 Unauthorized** → Raise AuthenticationError with clear message
  - Mock: API returns 401 + error JSON
  - Assert: raises `ElevenLabsAuthError` or similar
  - Assert: error message mentions invalid API key
- [ ] **500 Server Error** → Raise BackendError, don't retry
  - Mock: API returns 500
  - Assert: raises `ElevenLabsBackendError`
  - Assert: no retries (or limited retries only for 429)
- [ ] **4XX (bad request, not 401)** → Raise ValueError with validation details
  - Mock: 422 Unprocessable Entity (bad voice_id)
  - Assert: raises exception, message includes reason

### list_voices() Method Test Cases
- [ ] **200 OK** → returns list of VoiceInfo objects
  - Mock: `GET https://api.elevenlabs.io/v1/voices`
  - Assert: returns list of dicts with `voice_id`, `name`, `language`
  - Sample response: `[{voice_id: "XB0fD...", name: "Charlotte", language: "de"}]`
- [ ] **401 Unauthorized** → Raise AuthenticationError
  - Mock: 401
  - Assert: raises auth error
- [ ] Response schema validation
  - Assert: each voice has required fields (voice_id, name)
  - Assert: voice_id is non-empty string
  - Handles optional fields gracefully (description, category, etc.)

### Backend Interface Compliance
- [ ] Class inherits from `TTSBackend` ABC
- [ ] `synthesize(text, voice_id, output_format)` signature correct
- [ ] `list_voices()` returns list[VoiceInfo] (or compatible)
- [ ] `name` property returns "elevenlabs"
- [ ] Async methods properly marked (if using async/await)

### Error Handling & Robustness
- [ ] Malformed API responses (missing fields) → logged + exception
- [ ] Network timeouts → timeout exception propagated
- [ ] Empty text input → validation (may happen at API layer, not backend)
- [ ] Unknown voice_id → handled by ElevenLabs API (422), propagated correctly
- [ ] Config-driven API key and voice defaults
  - Assert: backend reads from config (ELEVENLABS_API_KEY env or config.yaml)
  - Assert: voice_id defaults to config value if not provided

## Implementation Steps
1. Install respx: `pip install respx`
2. Create `tests/test_elevenlabs_backend.py`
3. Write fixture: `elevenlabs_backend()` → instantiate backend with mock config
4. Write fixture: `mock_api()` → respx router (setup/teardown)
5. Implement `test_synthesize_success()` — 200 OK → bytes
6. Implement `test_synthesize_rate_limit_429()` — retry logic
7. Implement `test_synthesize_auth_401()` → exception
8. Implement `test_synthesize_server_error_500()` → exception
9. Implement `test_synthesize_bad_request_422()` → exception
10. Implement `test_list_voices_success()` — 200 OK → list
11. Implement `test_list_voices_auth_401()` → exception
12. Implement `test_list_voices_schema_validation()` — response has required fields
13. Implement `test_backend_inherits_abc()` — interface compliance
14. Implement `test_config_driven_api_key()` — respects config
15. Run: `pytest tests/test_elevenlabs_backend.py -v --cov=app.backends.elevenlabs`

## Mocking Details (respx)
```python
import respx
from httpx import AsyncClient

@pytest.fixture
def mock_api():
    with respx.mock:
        # respx will intercept all httpx requests
        yield respx
        # cleanup automatic

# Usage in tests:
async def test_synthesize_success(elevenlabs_backend, mock_api):
    mock_api.post("https://api.elevenlabs.io/v1/text-to-speech/voice_id").mock(
        return_value=httpx.Response(200, content=b"\xff\xfb...")  # MP3 header bytes
    )
    result = await elevenlabs_backend.synthesize("Hello", "voice_id", "mp3_44100_128")
    assert isinstance(result, bytes)
    assert len(result) > 0
```

## Blocking Issues
- [ ] **Clarify:** Max retries for 429? (Recommend: 3 retries max)
- [ ] **Clarify:** Backoff formula? (Recommend: exponential 1s, 2s, 4s with jitter)
- [ ] **Clarify:** Is output_format parameter used? Or hardcoded to "mp3_44100_128"?
- [ ] **Clarify:** Should synthesize() be async? (Architecture suggests yes)

## Notes
- respx is lighter than httpretty for httpx-based code
- Use real MP3 header bytes in mocks (`b"\xff\xfb"`) for realism
- Test retry behavior is critical for production resilience
- Don't test ElevenLabs' actual API behavior — only our code's handling
- Voice list should be cached (optional, but good practice) — test caching if implemented

## Depends On
- TTS-D1 (ElevenLabs Backend: synthesize() basic impl)
- TTS-D3 (Error handling: 429 retry, 401 auth, etc.)

---

## Research & Reference

### Key Patterns

- **respx für httpx-Mocking:** `import respx; @respx.mock async def test_...: respx.post("https://api.elevenlabs.io/...").mock(return_value=httpx.Response(200, content=b"..."))`. Alternativ: `with respx.mock: ...` als Context Manager. respx ist httpx-native und unterstützt async Tests ohne zusätzliche Setup.
- **pytest-asyncio für async Tests:** `@pytest.mark.asyncio async def test_synthesize_success(): ...` — `pytest-asyncio` Plugin nötig (`pip install pytest-asyncio`). Config in `pyproject.toml`: `[tool.pytest.ini_options] asyncio_mode = "auto"` → kein manuelles `@pytest.mark.asyncio` mehr nötig.
- **Fake MP3 Header Bytes:** `b"\xff\xfb\x90\x00"` — echte MP3 Frame-Header-Bytes. Tests können damit prüfen: `assert result[:2] == b"\xff\xfb"` für Basic-Sanity ohne Audio-Library. Für pure "bytes returned" Tests reicht auch `b"fake_audio_data"`.
- **Config Mock für Tests:** Backend braucht `config.backends.elevenlabs.api_key`. Einfachste Lösung: `from unittest.mock import MagicMock; config = MagicMock(); config.backends.elevenlabs.api_key.get_secret_value.return_value = "test-key"`. Oder Pydantic-Modell mit Testdaten instantiieren.
- **Retry-Timing in Tests:** Exponential Backoff testet man mit `unittest.mock.patch("asyncio.sleep")` oder `tenacity`-spezifischem Test-Modus (`wait=wait_none()` in Tests). Ohne Patch wären Tests mehrere Sekunden langsam. `respx` kann Sequenzen mocken: `.mock(side_effect=[httpx.Response(429, ...), httpx.Response(200, ...)])` — erster Call → 429, zweiter → 200.
- **`respx.MockRouter` mit Pattern-Matching:** `respx.post(url__regex=r"https://api.elevenlabs.io/v1/text-to-speech/.*")` — matcht beliebige voice_ids ohne Hardcoded ID im Test.

### Open Questions / Decisions

- **Retry-After Header im 429-Mock:** ElevenLabs gibt `Retry-After: 60` zurück. Test-Mock sollte das simulieren: `httpx.Response(429, headers={"Retry-After": "1"}, ...)` — 1s für schnelle Tests. Backend-Code liest den Header → Worker wartet entsprechend.
- **`asyncio_mode = "auto"` oder manuell?** `auto` macht alle async Test-Functions automatisch asyncio-Tests. Einfacher, aber ändert globales Pytest-Verhalten. → Empfehlung: `auto` für dieses Projekt (alles async).
- **Caching in `list_voices()` testen:** Wenn D2 einen TTL-Cache implementiert: Test braucht Cache-Invalidierung. `backend._voice_cache.clear()` oder Cache-TTL auf 0 für Tests setzen. Sicherstellen dass der Cache in Tests nicht zwischen Test-Runs leakt.

### Reference Links

- [respx docs]: https://lundberg.github.io/respx/
- [pytest-asyncio]: https://pytest-asyncio.readthedocs.io/
- [respx mock side_effect]: https://lundberg.github.io/respx/guide/#mocking-responses
- [unittest.mock.patch]: https://docs.python.org/3/library/unittest.mock.html#patch
- [MP3 Frame Header format]: https://en.wikipedia.org/wiki/MP3#File_structure
- [ElevenLabs Backend]: D1-elevenlabs-synthesize.md
- [Error Handling]: D3-elevenlabs-errors.md
