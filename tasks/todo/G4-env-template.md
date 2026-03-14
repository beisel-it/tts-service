# Task: .env-Template + Secrets Documentation
Shortcode: TTS-G4
Stage: todo
Status: refined → ready for research
Priority: P2
Owner: _unassigned_

---

## Definition of Done (testable)

- [ ] `.env.example` file created in repo root
- [ ] All required env vars listed with descriptions + example values
- [ ] Secrets clearly marked: `# SECRET: do not commit`, separate section
- [ ] Non-secrets vs. secrets distinguished by comment
- [ ] README section "Environment & Secrets" added with sourcing instructions
- [ ] `.gitignore` includes: `.env` (never committed)
- [ ] `.env.example` is commited (safe, uses dummy/public values)
- [ ] Tested: `source .env.example && env | grep TTS_` shows all vars
- [ ] Documented: where each secret comes from (service instructions)
- [ ] Documented: how to rotate secrets (manual process, steps)
- [ ] Documented: optional vs. required variables
- [ ] Security note: never log `.env`, never print secrets in startup logs

---

## Required Variables

### Service Configuration (non-secret)
```
TTS_SERVICE_API_KEY              (SECRET) — API key for /synthesize requests
TTS_SERVICE_HOST                 = "0.0.0.0"
TTS_SERVICE_PORT                 = 8080
TTS_WORKER_CONCURRENCY           = 3
TTS_DEFAULT_BACKEND              = "elevenlabs"
```

### Storage Configuration (non-secret paths)
```
TTS_STORAGE_PATH                 = "/data/audio"
TTS_STORAGE_PUBLIC_BASE_URL      = "https://tts.service/audio"
TTS_STORAGE_CLEANUP_AFTER_DAYS   = 7
```

### Queue Configuration (non-secret)
```
TTS_QUEUE_BACKEND                = "sqlite"
TTS_QUEUE_SQLITE_PATH            = "/data/jobs.db"
```

### ElevenLabs Backend (SECRET)
```
ELEVENLABS_API_KEY               (SECRET) — from elevenlabs.io dashboard
TTS_ELEVENLABS_DEFAULT_VOICE_ID  = "XB0fDUnXU5powFXDhCwa"  (public, example)
TTS_ELEVENLABS_MODEL_ID          = "eleven_multilingual_v2"
TTS_ELEVENLABS_OUTPUT_FORMAT     = "mp3_44100_128"
```

### Webhook Configuration
```
WEBHOOK_SIGNING_SECRET           (SECRET) — random string, consumer validates
TTS_WEBHOOK_TIMEOUT_SECONDS      = 10
TTS_WEBHOOK_RETRY_ATTEMPTS       = 3
```

### Optional: Azure Backend (Phase 2, disabled by default)
```
TTS_AZURE_ENABLED                = false
AZURE_SPEECH_KEY                 (SECRET, if enabled)
TTS_AZURE_REGION                 = "westeurope"
TTS_AZURE_DEFAULT_VOICE          = "de-DE-KatjaNeural"
```

### Optional: Piper Backend (Phase 2, local/self-hosted)
```
TTS_PIPER_ENABLED                = false
TTS_PIPER_MODEL_PATH             = "/models/de_DE-thorsten-high.onnx"
```

### Logging (non-secret)
```
LOG_LEVEL                        = "info"  (debug|info|warning|error)
```

---

## Steps

### Phase 1: Create .env.example
1. Create `.env.example` in repo root
2. Add all vars from "Required Variables" section above
3. Use safe, public example values (e.g., dummy API keys like `sk-test-xxx`, public model names)
4. Comment each line with brief description + data type
5. Group by subsystem (Service, Storage, Queue, Backends)
6. Clearly mark `(SECRET)` vars with banner comment

### Phase 2: Create .env.development (optional, for local testing)
7. Copy `.env.example` → `.env.development`
8. Fill in real local values (e.g., actual ElevenLabs test key if available, or skip)
9. Document: `.env.development` is NOT committed, used locally only
10. Add to `.gitignore`: `.env.development`

### Phase 3: Document in README
11. Add section: "Environment Variables"
12. Explain: `.env` is loaded by app on startup (pydantic Settings)
13. Source instructions:
    - Docker: use `env_file: .env` in docker-compose.yml
    - Local dev: `source .env.example && python -m app.main`
14. List each var: name, type, required/optional, default, description

### Phase 4: Secrets Management Documentation
15. Create section: "Secrets & Security"
16. Document each SECRET var origin:
    - `ELEVENLABS_API_KEY`: How to get from elevenlabs.io
    - `TTS_SERVICE_API_KEY`: Generate random (e.g., `python -c "import secrets; print(secrets.token_hex(32))"`)
    - `WEBHOOK_SIGNING_SECRET`: Generate same way
17. Document rotation process:
    - For ElevenLabs: create new key in dashboard, update `.env`, restart service, test
    - For API key: generate new one, update all consumers, restart
    - For webhook secret: change in `.env` + notify consumer of new secret (for signature validation)
18. Warning: "Never commit `.env`; use `.env.example` for safe reference"
19. Warning: "Never log env vars or secret values; sanitize logs"

### Phase 5: Testing & Validation
20. Test: `bash -n .env.example` (syntax check, if using bash syntax)
21. Test: `grep -v "^#" .env.example | grep "=" | wc -l` (count vars)
22. Test: `docker-compose --env-file .env.example config` (parse with docker-compose)
23. Test: Create `.env` from `.env.example`, set real values, start app, check logs for missing vars
24. Document: Add `Configuration Checklist` to README

---

## Blocking

- None — can be done independently, but should precede task G2 (docker-compose.yml)

---

## Notes

### Generation of Random Secrets
```bash
# API Key (32 hex = 64 bits entropy)
python -c "import secrets; print('TTS_SERVICE_API_KEY=' + secrets.token_hex(32))"

# Webhook Signing Secret (same)
python -c "import secrets; print('WEBHOOK_SIGNING_SECRET=' + secrets.token_hex(32))"
```

### Example `.env.example` header
```
# ============================================================================
# TTS Service Configuration — Environment Variables
# ============================================================================
# IMPORTANT: This file is an EXAMPLE. Do NOT commit your actual .env file.
# Copy this to .env and fill in real values for your environment.
#
# SECRETS (marked below): Never commit to git. Rotate periodically.
# Non-secrets: Safe to share, documented for clarity.
# ============================================================================
```

### Checking for Secret Leaks Pre-Commit
Future CI rule: `git diff --cached | grep -i "api.key\|secret" | grep -v ".example"`

---

## Related Tasks
- G2 (Docker + docker-compose.yml) — uses env_file
- G3 (Nginx config) — may reference some public vars
- All backend tasks (D1, D3) — consume env vars

---

## Research & Reference

### Key Patterns

- **`pydantic-settings` für Env-Var-Laden:** `from pydantic_settings import BaseSettings` — liest automatisch Env-Vars (uppercase), `.env`-Datei via `model_config = SettingsConfigDict(env_file=".env")`. Nested Config via `model_config = SettingsConfigDict(env_nested_delimiter="__")`: `TTS__STORAGE__PATH` → `config.storage.path`. Eleganter als manuelles `os.environ.get()`.
- **`SecretStr` für Sensitive Vars:** `api_key: SecretStr` — wird in `repr()` und Logs als `'**********'` angezeigt. Wert abrufen: `config.api_key.get_secret_value()`. Verhindert versehentliches Logging.
- **`.env.example` commiten, `.env` nicht:** `.gitignore` enthält `.env` (und `.env.*` außer `.env.example`). `.env.example` mit Dummy-Werten ist safe zu commiten — es ist die Dokumentation der Required Vars.
- **`secrets.token_hex(32)` für Key-Generierung:** 32 Bytes = 256 Bit Entropie, als 64-char Hex-String. Ausreichend für API-Keys und Signing-Secrets. Einfachste sichere Methode ohne externe Tools.
- **Startup-Validation:** Pydantic BaseSettings wirft `ValidationError` beim Import wenn Required Fields fehlen. Keine eigene Validation nötig. Fehlermeldung enthält den fehlenden Field-Namen. → App crasht beim Start mit klarer Meldung statt runtime-Fehler.

### Open Questions / Decisions

- **Flat oder nested Env-Vars?** `ELEVENLABS_API_KEY` (flat, gängig) vs `TTS__BACKENDS__ELEVENLABS__API_KEY` (nested via Delimiter, aber hässlich). → Empfehlung: Flat für Secrets (`ELEVENLABS_API_KEY`, `TTS_SERVICE_API_KEY`), nested Delimiter nur für non-secrets wenn nötig. Einfacher für den Operator.
- **`.env.development` committen?** Nie — enthält echte Werte. Stattdessen: `.env.example` mit Kommentaren die erklären was jeder Wert ist und wo man ihn findet.
- **`LOG_LEVEL` als Env-Var oder Config-Datei?** Env-Var ist flexibler (kann per Container überschrieben werden). → `LOG_LEVEL` als Env-Var, Default `"info"` in Settings-Klasse.

### Reference Links

- [pydantic-settings docs]: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- [pydantic SecretStr]: https://docs.pydantic.dev/latest/concepts/types/#secret-types
- [secrets module]: https://docs.python.org/3/library/secrets.html
- [12-Factor App Config]: https://12factor.net/config
- [Config YAML spec]: ARCHITECTURE.md §7
- [G2 docker-compose env_file]: G2-docker-compose.md
