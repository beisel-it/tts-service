# Task: Backend Router — Configuration-based Selection
**Shortcode:** TTS-E1  
**Stage:** todo  
**Status:** todo  
**Priority:** P1

## Description
Implementiere den Backend Router (`app/backends/router.py`), der basierend auf Konfiguration und Request-Parametern das passende TTS-Backend auswählt. Der Router instantiiert Backends lazy, cached Instanzen, und ermöglicht Tests mit Mock-Backends. Diese Task ist Fundament für alle Backend-Aufrufe (D1+, C2).

**Kontext:**
- Router wird vom Worker (C2) und von der API (B1) verwendet um zu entscheiden: "Welches Backend nutze ich jetzt?"
- Config definiert: `default_backend: "elevenlabs"` sowie welche Backends enabled sind
- Request kann Backend override durch `?backend=xyz` oder direkt im Request-Body angeben
- Router validiert: "Ist dieses Backend enabled/konfiguriert?"
- Lazy-Init: Backends werden erst bei erstem Zugriff initialisiert (nicht alle beim Start laden)

## Definition of Done

### 1. Router-Klasse
- ✅ `class BackendRouter:` mit `__init__(config: Config, logger)` 
- ✅ Config speichern, Logger initialisieren
- ✅ Internal cache für Backend-Instanzen: `_backends: Dict[str, TTSBackend]`

### 2. Backend-Auswahl Logik
- ✅ `get_backend(backend_name: str | None) -> TTSBackend` Methode
- ✅ Falls `backend_name` ist None → nutze `config.default_backend`
- ✅ Falls `backend_name` gesetzt → validiere ob enabled/konfiguriert (sonst raise `InvalidBackendError`)
- ✅ Rückgabe: cached TTSBackend-Instanz (oder neu erzeugt falls nicht im Cache)
- ✅ Exception bei unbekanntem/disabled Backend: `InvalidBackendError(f"Backend '{backend_name}' not configured or disabled")`

### 3. Backend-Instantiation (Lazy Loading)
- ✅ Jedes Backend-Modul (`elevenlabs.py`, `azure.py`, `polly.py`, `piper.py`) exportiert `class XyzBackend(TTSBackend)` + `def create_xyz_backend(config) -> XyzBackend`
- ✅ Router ruft passende `create_*_backend(config.backends[name])` auf
- ✅ Fehler beim Init (z.B. fehlender API-Key) → `BackendInitError(f"Failed to initialize {name}: ...")`
- ✅ Cache-Treffer: Router gibt gecachte Instanz zurück (keine Re-Init)

### 4. list_available_backends()
- ✅ `list_available_backends() -> Dict[str, VoiceInfo[]]`
- ✅ Für alle enabled Backends: `voices = backend.list_voices()` aufrufen
- ✅ Rückgabe: `{"elevenlabs": [...], "azure": [...], ...}`
- ✅ Lazy: Nur für Backends die momentan im Cache sind (oder bei expli zitem Request alle abfragen)

### 5. Configuration Validation
- ✅ Im Router: Wenn `config.backends.<name>.enabled=false` → wird dieses Backend nicht initialisiert
- ✅ Validation: "Hat TTS-Aufruf einen gültigen Backend-Namen mitbekommen?" → Prüfung im Router

### 6. Error Handling
- ✅ Custom Exceptions:
  - `InvalidBackendError` — Backend unbekannt oder disabled
  - `BackendInitError` — Backend konnte nicht initialisiert werden
  - `BackendUnavailableError` — Backend ist konfiguriert, aber aktuell nicht erreichbar (z.B. API Key invalid)
- ✅ Diese Exceptions sind zu Fangen in C2 + B1, um später Fallback-Logik zu treffen

### 7. Testing Support
- ✅ Router akzeptiert optional `backend_overrides: Dict[str, TTSBackend]` im Init für Tests
- ✅ `router = BackendRouter(config, logger, backend_overrides={"elevenlabs": mock_backend})`
- ✅ Testbar: Mock-Backend wird zurückgegeben statt echtem zu laden

### 8. Logging
- ✅ Log beim Init: `Initializing Backend Router`
- ✅ Log beim Laden eines neuen Backends: `Loading backend 'elevenlabs'` (INFO)
- ✅ Log bei Cache-Hit: `Using cached backend 'elevenlabs'` (DEBUG)
- ✅ Log bei InvalidBackendError: `Backend 'xyz' not available` (WARN)

### 9. Type Hints & Docstrings
- ✅ Vollständige Type Hints für alle Methoden
- ✅ Docstrings erklären Verhalten (lazy loading, caching, error cases)

## Implementation Steps

1. **Exception-Klassen definieren:** `InvalidBackendError`, `BackendInitError`, `BackendUnavailableError` in `backends/router.py`
2. **BackendRouter-Klasse schreiben:**
   - `__init__(config, logger, backend_overrides=None)`
   - `_backends` Dict initialisieren
3. **get_backend() implementieren:**
   - Auswahl-Logik (None → default, else → validieren)
   - Cache-Check
   - Lazy init mit `create_*_backend()`
4. **create_*_backend() für jedes Backend schreiben** — aufgerufen vom Router via dynamic dispatch
5. **list_available_backends() implementieren**
6. **Unit-Tests schreiben:**
   - Default backend auswählen
   - Custom backend auswählen
   - Invalid backend → InvalidBackendError
   - Cache-Hit (zweiter Aufruf gibt gleiche Instanz)
   - Mock-Override in Tests funktioniert
   - list_available_backends() ruft backend.list_voices() auf
7. **Docstrings + Type Hints durchgehen**

## Blocking Factors / Dependencies
- **Depends on:**
  - TTS-A1 (Config System muss die backends[].enabled + default_backend definieren)
  - TTS-D1, D2, D3 (Mindestens ElevenLabs Backend muss TTSBackend ABC implementieren)
  - Base Backend ABC (`backends/base.py`) muss definiert sein
- **Implementierung blockiert:**
  - TTS-C2 (Worker-Loop braucht Router um Backend zu wählen)
  - TTS-B1 (API /synthesize braucht Router)
- **Keine externen Service-Dependencies** — rein Software-Architektur

## Acceptance Criteria for Testing & Handoff

1. ✅ `pytest tests/test_router.py::test_default_backend` — get_backend(None) gibt default backend zurück
2. ✅ `pytest tests/test_router.py::test_custom_backend` — get_backend("azure") gibt azure backend zurück
3. ✅ `pytest tests/test_router.py::test_invalid_backend` — get_backend("nonexistent") wirft InvalidBackendError
4. ✅ `pytest tests/test_router.py::test_disabled_backend` — get_backend("disabled_backend") wirft InvalidBackendError
5. ✅ `pytest tests/test_router.py::test_cache_hit` — get_backend("elevenlabs") 2× aufgerufen → gleiche Instanz
6. ✅ `pytest tests/test_router.py::test_mock_override` — BackendRouter mit mock_override arbeitet korrekt
7. ✅ `pytest tests/test_router.py::test_list_available_backends` — list_available_backends() gibt Dict mit voices zurück
8. ✅ `pytest tests/test_router.py::test_lazy_init` — Backend wird erst beim ersten get_backend() initialisiert
9. ✅ Logging validierbar: Debug logs für Cache-Hit, Info logs für Init
10. ✅ Type Hints vollständig + mypy clean

---

**Ready für Code-Phase:** Router-Implementierung, Unit-Tests, Integration mit C2/B1 wird danach durchgeführt
