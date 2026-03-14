# Task: Backend-Stubs (Azure, Polly, Piper)
Shortcode: TTS-F1
Stage: todo
Status: ready-for-research
Priority: P2
Depends on: TTS-A1

## Definition of Done

### Files Created
- `app/backends/azure.py` — AzureBackend class (stub)
- `app/backends/polly.py` — PollyBackend class (stub)
- `app/backends/piper.py` — PiperBackend class (stub)
- `app/backends/__init__.py` — exports all backend classes

### Class Requirements (per backend stub)
Each backend class:
- ✅ Inherits from `TTSBackend` (from `app.backends.base`)
- ✅ Implements `async def synthesize()` → `raise NotImplementedError("Azure backend not yet implemented")`
- ✅ Implements `def list_voices()` → `raise NotImplementedError()`
- ✅ Implements `@property def name()` → returns backend name (e.g., "azure", "polly", "piper")
- ✅ Docstring referencing architecture spec section 4.2/4.3/4.4

### Backend Router Integration
- `app/backends/base.py` exports `get_backend(name: str, config: Config) -> TTSBackend` factory
- Router checks: if `backend_name` in config.backends and `backends[backend_name].enabled == true`
- If disabled/unknown: raises `ValueError(f"Backend '{name}' not enabled or not found")` with helpful message
- If stub: raises `NotImplementedError` (only when user tries to actually use it)

### Test Verification
- `pytest tests/test_backends.py::test_stub_backends_instantiate` — all stubs can be created
- `pytest tests/test_backends_get_backend_router` — router correctly instantiates backends
- `pytest tests/test_backend_disabled_error` — disabled backend raises helpful error

## Implementation Steps

1. Create three stub files (azure.py, polly.py, piper.py) under `app/backends/`
   - Each implements TTSBackend ABC with NotImplementedError
   - Copy template structure from base.py example

2. Update `app/backends/__init__.py`
   - Import all three backend classes
   - Export in `__all__`

3. Implement `get_backend()` factory in `base.py` (or new `router.py`)
   - Reads config.backends[backend_name]
   - Checks `.enabled` flag
   - Instantiates matching class
   - Raises ValueError if disabled, NotImplementedError if called but stub

4. Add basic tests to `tests/test_backends.py`
   - Instantiation of all stubs works
   - Router picks correct backend by name
   - Disabled backend → ValueError
   - Stub method call → NotImplementedError

5. Update app main config to recognize all backend names
   - Ensure config.yaml has entries for azure, polly, piper with `enabled: false` (default)

## Dependencies & Blockers
- ✅ Depends on: TTS-A1 (Config system must be in place)
- ⏳ Blocks: None (stubs don't block other work; Phase 2 backends use same interface)
- No blockers identified

## Notes
- Architecture spec: Section 4.2 (Azure), 4.3 (Polly), 4.4 (Piper)
- Priority raised to P2 because router pattern unlocks parallel Phase-2 backend work
- Stubs follow "explicit NotImplementedError" pattern; no silent failures

---

## Research & Reference

### Key Patterns

- **Factory-Funktion als Backend-Router:** `get_backend(name: str, config: Config) -> TTSBackend` in `base.py`. Simple `match`-Statement oder Dict-Mapping: `{"elevenlabs": ElevenLabsBackend, "azure": AzureBackend, ...}`. Prüft `config.backends[name].enabled` vor Instantiierung.
- **`enabled`-Flag im Config:** Jedes Backend hat `enabled: bool` in seiner Config-Sektion. Disabled Backends können instantiiert werden (für Import-Tests), aber Methodenaufruf → `NotImplementedError`. Disabled prüfen im Router, nicht im Backend selbst.
- **ABC enforce:** Python ABC wirft `TypeError` wenn eine Klasse nicht alle `@abstractmethod`s implementiert. Stubs müssen alle ABCs implementieren — sonst `TypeError: Can't instantiate abstract class`. Selbst `raise NotImplementedError()` im Body reicht.
- **`__init__.py` als öffentliche API:** `from app.backends import get_backend, ElevenLabsBackend, AzureBackend` — konsistenter Import für den Rest des Projekts. `__all__` explizit setzen.
- **Docstring-Referenz auf Architecture:** Jeder Stub-Kommentar zeigt auf `ARCHITECTURE.md §4.2/4.3/4.4` — Implementierer wissen sofort wo die Spec liegt.

### Open Questions / Decisions

- **Router in `base.py` oder eigenem `router.py`?** → Empfehlung: eigenes `app/backends/router.py`. `base.py` bleibt reine Abstraktion. Router importiert alle konkreten Backends — circular imports vermeiden indem Router nur in `__init__.py` re-exportiert wird.
- **`enabled: false` → ValueError oder NotImplementedError?** Semantisch unterschiedlich: `disabled` ist eine Konfigurationsentscheidung (ValueError/RuntimeError mit Hinweis "enable in config.yaml"), `not_implemented` ist ein Code-Gap (NotImplementedError). → Router wirft `RuntimeError("Backend 'azure' is disabled in config")`, Stub-Methods werfen `NotImplementedError`.

### Reference Links

- [Python ABC]: https://docs.python.org/3/library/abc.html
- [Backend Interface]: ARCHITECTURE.md §4 (TTSBackend ABC)
- [Azure Backend Spec]: ARCHITECTURE.md §4.2
- [Polly Backend Spec]: ARCHITECTURE.md §4.3
- [Piper Backend Spec]: ARCHITECTURE.md §4.4
- [Config (backends section)]: ARCHITECTURE.md §7
