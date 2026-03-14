# Task: ElevenLabs Backend — list_voices()
Shortcode: TTS-D2
Stage: todo
Status: ready for research
Priority: P3

## Summary
Implement `list_voices()` method on ElevenLabsBackend to fetch and parse available voices from the ElevenLabs API. Must support language filtering and provide structured VoiceInfo objects for internal use and admin endpoint exposure.

## Definition of Done (testable criteria)
- ✅ `ElevenLabsBackend.list_voices()` returns `list[VoiceInfo]`
- ✅ Fetches `GET https://api.elevenlabs.io/v1/voices` with auth header `xi-api-key`
- ✅ Parses response: extracts `voice_id`, `name`, `language`, `description`
- ✅ VoiceInfo dataclass includes: `id`, `name`, `language`, `category` (preview_url optional)
- ✅ Caching: result cached for 24h to avoid rate-limit churn
- ✅ Error handling: delegates to D3 exception hierarchy (RateLimitError, AuthError, etc.)
- ✅ Test coverage: mocked API call with sample voice list, validates parsing + caching behavior
- ✅ Integration with `GET /admin/voices` endpoint returns filtered list by language (default: all)

## Implementation Steps
1. Create `VoiceInfo` dataclass in `app/backends/base.py` with fields: id, name, language, category, preview_url (optional)
2. Implement `list_voices()` in `app/backends/elevenlabs.py`:
   - HTTP GET to `/v1/voices` endpoint
   - Extract `voices[]` from response
   - Map each voice to VoiceInfo
   - Return sorted by `name`
3. Add cache decorator (24h TTL) to avoid redundant API calls
4. Integrate into `app/api/routes_admin.py` — expose via `GET /admin/voices?language=de` query param
5. Write test in `tests/test_elevenlabs_backend.py`: mock response, verify parsing, cache hit

## Blocking Factors
- None — depends only on TTS-D1 (Backend base class exists)

## Notes
- ElevenLabs API docs: https://elevenlabs.io/docs/api-reference/voices
- Language field: use ISO 639-1 code (de, en, fr, etc.)
- Sample response structure (inspect live ElevenLabs API for exact fields)
- Caching is important: many requests to `/admin/voices` will occur during development/testing
