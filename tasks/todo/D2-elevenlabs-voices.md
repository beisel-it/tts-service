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

---

## Research & Reference

### Key Patterns

- **ElevenLabs Voices Endpoint:** `GET https://api.elevenlabs.io/v1/voices` — selber Auth-Header (`xi-api-key`). Response: `{"voices": [{"voice_id": "...", "name": "...", "labels": {"language": "de"}, ...}]}`. Language ist in `labels`-Dict, nicht als Top-Level-Feld.
- **VoiceInfo Dataclass:** `@dataclass class VoiceInfo: id: str; name: str; language: str | None; category: str | None` — in `base.py` definiert, damit alle Backends denselben Typ zurückgeben.
- **TTL-Cache mit cachetools:** `from cachetools import TTLCache, cached; cache = TTLCache(maxsize=1, ttl=300)`. Für Methoden auf Instances: `cached(cache=cache)` funktioniert nicht direkt — besser: manuell mit `_cache: dict` + Timestamp-Check. Oder `async_lru` für async-Methoden.
- **Sprachcode-Mapping:** ElevenLabs gibt `"labels": {"accent": "american", "language": "english"}` zurück — kein ISO-Code. Mapping nötig: `{"english": "en", "german": "de", "french": "fr", ...}`. Oder direkt den Raw-String zurückgeben und Consumer entscheidet.
- **list_voices() ist sync oder async?** ABC definiert `def list_voices()` als sync. Da es einen HTTP-Call macht, sollte es `async def list_voices()` sein. → ABC in base.py entsprechend anpassen.

### Open Questions / Decisions

- **Sprachcode normalisieren?** ElevenLabs gibt "german" statt "de" zurück. Soll VoiceInfo.language "german" oder "de" sein? → Empfehlung: lowercase ISO-639-1 ("de") für Konsistenz mit anderen Backends. Mapping-Tabelle in D2 implementieren.
- **Cache-Dauer:** 24h im DoD, aber 5 min in B3-Task. → Einigung: 5 Minuten für `/admin/voices` (Interactive), 24h für interne Calls. Oder: ein globaler TTL-Cache, konfigurierbar. Entscheidung dokumentieren.
- **`list_voices()` async?** Wenn sync im ABC: blocking HTTP-Call in async context → Problem. → ABC muss `async def list_voices()` sein.

### Reference Links

- [ElevenLabs Voices API]: https://elevenlabs.io/docs/api-reference/voices/get-voices
- [cachetools TTLCache]: https://cachetools.readthedocs.io/en/stable/#cachetools.TTLCache
- [async_lru (async cache)]: https://pypi.org/project/async-lru/
- [VoiceInfo + ABC]: ARCHITECTURE.md §4 (TTSBackend Interface)
- [Admin endpoint]: B3-route-admin.md
