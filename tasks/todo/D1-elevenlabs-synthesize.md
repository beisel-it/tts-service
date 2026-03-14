# Task: ElevenLabs Backend — synthesize()
Shortcode: TTS-D1
Stage: todo
Status: ready for research
Priority: P1

## Definition of Done

- **Class Implementation**: `class ElevenLabsBackend(TTSBackend)` in `app/backends/elevenlabs.py`
- **Synthesize Method**: 
  - Signature: `async def synthesize(self, text: str, voice_id: str, output_format: str = "mp3_44100_128") -> bytes:`
  - Calls: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
  - Model: `eleven_multilingual_v2` (hardcoded)
  - Output format: `mp3_44100_128` (default, overridable)
  - Returns: raw MP3 bytes (no wrapper)
  - Auth: `xi-api-key` header from config (`backends.elevenlabs.api_key`)
  - Timeout: 30 seconds per request
- **Error Handling**:
  - Handle 401 (invalid API key) → raise `AuthenticationError`
  - Handle 429 (rate limit) → raise `RateLimitError` with retry-after info
  - Handle 400 (invalid voice/text) → raise `BadRequestError` with details
  - Handle network errors → raise `NetworkError`
  - Include ElevenLabs response content in exception message for debugging
- **Request Validation**:
  - Text length must be > 0 and <= 5000 characters (per ElevenLabs limits)
  - voice_id must be non-empty string
  - Raise `ValueError` for invalid inputs
- **Config Integration**:
  - Read from `config.backends.elevenlabs.api_key` (required, env: `ELEVENLABS_API_KEY`)
  - Read from `config.backends.elevenlabs.model_id` (default: `eleven_multilingual_v2`)
  - Read from `config.backends.elevenlabs.output_format` (default: `mp3_44100_128`)
- **Testability**:
  - Unit tests with mocked HTTP client (httpx mocks)
  - Test successful synthesis (mock 200 response with bytes)
  - Test all error cases (401, 429, 400, network timeout)
  - Test request shape (headers, body, URL path)
  - Parameterized tests for different voice_ids and output formats

## Implementation Steps

1. **Create `app/backends/elevenlabs.py`**:
   - Import `HTTPClient` async client (httpx), config loader, exceptions
   - Implement `ElevenLabsBackend(TTSBackend)` class
   - Constructor: `__init__(config: Config)` — extract API key + model + format
   - Implement `synthesize()` method (async)
   - Implement `name` property (return "elevenlabs")

2. **Define Exception Hierarchy** (in `app/backends/base.py` or new `app/exceptions.py`):
   - `TTSBackendError` (base)
   - `AuthenticationError`
   - `RateLimitError` (with retry_after field)
   - `BadRequestError`
   - `NetworkError`

3. **Update `app/backends/__init__.py`**:
   - Export `ElevenLabsBackend`, exception classes

4. **Integration with Config**:
   - Ensure `config.yaml` template includes elevenlabs section (api_key, model_id, output_format)
   - Validate that `ELEVENLABS_API_KEY` is set before instantiating

5. **Tests** (`tests/test_elevenlabs_backend.py`):
   - Mock httpx.AsyncClient
   - Success case: valid text → verify request shape → return MP3 bytes
   - Auth error (401) → raise `AuthenticationError`
   - Rate limit (429) → raise `RateLimitError`
   - Bad request (400) → raise `BadRequestError`
   - Network timeout → raise `NetworkError`
   - Input validation tests (empty text, oversized text, invalid voice_id)

## Blocking / Dependencies

- **Depends on**: 
  - TTS-A1 (Config-System) — needs config.backends.elevenlabs section
  - TTS-B0 or equivalent (Backend Base Class) — `app/backends/base.py` must define `TTSBackend` ABC
- **Blocks**: 
  - TTS-C2 (Worker-Loop) — can't process jobs until backend is working
  - TTS-E1 (Backend Router) — needs concrete backend implementation
- **External**:
  - ElevenLabs API key (requires account at elevenlabs.io)
  - Network access to api.elevenlabs.io

## Notes

- MP3 128kbps is sufficient for speech synthesis (no need for higher bitrates)
- ElevenLabs multilingual model supports German + other languages in one model
- Default voice_id (`XB0fDUnXU5powFXDhCwa` = Charlotte) is a reasonable EN/DE choice; config allows override
- Rate limits: ElevenLabs free tier is ~10k characters/month; paid plans scale. Worker should respect 429 backoff.
- Response is raw bytes — no JSON wrapper, goes straight to storage

---

## Research & Reference

### Key Patterns

- **httpx.AsyncClient für HTTP:** `async with httpx.AsyncClient() as client: response = await client.post(...)` — httpx ist der Standard für async HTTP in FastAPI-Projekten. Gleiche Library wie FastAPI intern nutzt. Timeout via `httpx.Timeout(30.0)`.
- **ElevenLabs API Endpoint:** `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` — voice_id im Path, output_format als Query-Parameter. Body: `{"text": "...", "model_id": "eleven_multilingual_v2"}`.
- **Auth Header:** `xi-api-key: {api_key}` — nicht `Authorization: Bearer`. ElevenLabs-spezifisch.
- **Response als Bytes:** Bei erfolgreichem Request (200) gibt ElevenLabs direkt den Audio-Stream zurück (Content-Type: `audio/mpeg`). Kein JSON-Wrapper. `response.content` gibt `bytes` zurück.
- **TTSBackend ABC:** `synthesize()` ist `async` — wichtig, da httpx-Calls awaitable sind. ABC in `base.py` muss `async def synthesize()` definieren.
- **Client-Lifecycle:** `AsyncClient` am besten als Instance-Variable im Backend, einmal erstellt im `__init__`, nicht per-call. Mit `await client.aclose()` bei Teardown. Alternativ: `@asynccontextmanager`.

### Open Questions / Decisions

- **5000-Zeichen-Limit hardcoded oder aus Config?** ElevenLabs erlaubt bis 5000 Zeichen pro Request. Soll die Validation in `synthesize()` oder bereits in der API-Route (B1) stattfinden? → Empfehlung: beide. B1 validiert am Eingang (422 zurück), D1 validiert nochmal defensiv (ValueError).
- **output_format als Parameter oder Config-only?** Die Methoden-Signatur hat `output_format` als Parameter. Realistisch wird immer `mp3_44100_128` genutzt. → Parameter behalten für Flexibilität, Default aus Config.
- **httpx vs aiohttp?** httpx ist moderner, bessere Typing-Support, kleinere API-Surface. Einigung auf httpx als einzige HTTP-Library im Projekt.

### Reference Links

- [ElevenLabs TTS API]: https://elevenlabs.io/docs/api-reference/text-to-speech/convert
- [ElevenLabs Error Codes]: https://elevenlabs.io/docs/api-reference/errors
- [httpx AsyncClient]: https://www.python-httpx.org/async/
- [TTSBackend ABC]: ARCHITECTURE.md §4
- [Config (elevenlabs section)]: ARCHITECTURE.md §7
