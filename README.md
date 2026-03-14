# 🔊 tts-service

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-eleven__multilingual__v2-6B21A8)](https://elevenlabs.io)
[![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-Private-red)](.)
[![Coverage](https://img.shields.io/badge/Coverage-≥80%25-brightgreen)](.)

> **Text rein → Job-ID + Audio-URL zurück → Audio erscheint dort wenn fertig.**  
> Asynchroner TTS-Webservice für deutsche Sprachsynthese. Wir sind kein CDN — wir synthetisieren einmal, der Consumer cached selbst.

---

## ✨ Features

- 🚀 **Promise-URL-Modell** — sofortige Antwort mit deterministischer Audio-URL, keine Wartezeit
- 🔄 **Async Queue** — SQLite-basierte Job-Queue mit Worker-Loop, horizontal skalierbar
- 🎙️ **Multi-Backend** — ElevenLabs primär, Azure/Polly als Fallback-Kette
- 🔐 **API-Key Auth** — `X-API-Key` Header auf allen Endpunkten (außer `/health`)
- 🪝 **Webhooks** — optionaler Callback nach Fertigstellung mit Retry-Logik
- 📦 **Docker-ready** — `docker-compose up` und fertig
- 🧪 **Testabdeckung ≥80%** — pytest + coverage als pre-commit Gates

---

## 🏗️ Architektur

```
Consumer
  │
  ├─ POST /synthesize ──→ Job anlegen → 201 + audio_url (pending)
  │
  ├─ GET  /jobs/{id}  ──→ Status polling
  │
  └─ Webhook callback ──→ Push wenn fertig
          │
          ▼
    ┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
    │  FastAPI API │────▶│ SQLite Queue│────▶│  Worker Process  │
    └─────────────┘     └─────────────┘     └──────┬───────────┘
                                                    │
                                          ┌─────────▼─────────┐
                                          │  Backend Router    │
                                          │  ElevenLabs → ...  │
                                          └─────────┬──────────┘
                                                    │
                                          ┌─────────▼──────────┐
                                          │  Local Storage      │
                                          │  /data/audio/{hash} │
                                          └────────────────────┘
```

Vollständige Architektur-Doku: [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md)

---

## 🚀 Quickstart

### Mit Docker Compose

```bash
cp .env.example .env
# .env befüllen (ELEVENLABS_API_KEY, TTS_API_KEY, etc.)

docker-compose up -d
```

API läuft auf `http://localhost:8080`.

### Lokal (Dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Config anpassen
cp .env.example .env
cp config.yaml config.local.yaml

uvicorn app.main:app --reload
```

---

## 📡 API

### `POST /synthesize`

```http
POST /synthesize
X-API-Key: your-api-key
Content-Type: application/json

{
  "text": "Hallo Welt, das ist ein Test.",
  "article_id": "article-123",        // optional, für Idempotenz
  "voice": "de-default",              // optional
  "backend": "elevenlabs",            // optional
  "webhook_url": "https://..."        // optional
}
```

**Response 201 (neu):**
```json
{
  "job_id": "tts_7f3a2b1c",
  "status": "pending",
  "audio_url": "https://tts.service/audio/7f3a/7f3a2b1c...mp3",
  "poll_url": "https://tts.service/jobs/tts_7f3a2b1c",
  "cached": false
}
```

**Response 200 (bereits vorhanden):**
```json
{
  "job_id": "tts_7f3a2b1c",
  "status": "done",
  "audio_url": "https://tts.service/audio/7f3a/7f3a2b1c...mp3",
  "cached": true
}
```

### `GET /jobs/{job_id}`

```http
GET /jobs/tts_7f3a2b1c
X-API-Key: your-api-key
```

```json
{
  "job_id": "tts_7f3a2b1c",
  "status": "done",
  "audio_url": "https://...",
  "duration_seconds": 4.2,
  "chars_processed": 29,
  "backend_used": "elevenlabs",
  "created_at": "2026-03-14T12:00:00Z",
  "completed_at": "2026-03-14T12:00:05Z"
}
```

### `GET /health`

```json
{"status": "healthy"}
```

---

## ⚙️ Konfiguration

Alle Werte via `config.yaml` + `.env` (Env überschreibt YAML):

Auth tokens können als `api_keys:` Liste in `config.yaml` gepflegt werden (alle gleichberechtigt).

| Variable | Beschreibung | Pflicht |
|----------|-------------|---------|
| `TTS_API_KEY` | API-Key(s) für Auth (single or list in config.yaml) | ✅ |
| `ELEVENLABS_API_KEY` | ElevenLabs Credentials | ✅ |
| `TTS_STORAGE__PUBLIC_BASE_URL` | Basis-URL für Audio-URLs | ✅ |
| `TTS_SQLITE_PATH` | Pfad zur jobs.db | ❌ (default: `/data/jobs.db`) |
| `TTS_WORKER__POLLING_INTERVAL_SECONDS` | Polling-Intervall in Sekunden | ❌ (default: `2`) |

Vollständige Liste: [`.env.example`](.env.example)

---

## 🧪 Tests & Quality Gates

```bash
# Tests mit Coverage
pytest

# Linter
ruff check app/ tests/
ruff format app/ tests/

# Pre-commit installieren (einmalig)
pre-commit install
```

Pre-commit Hooks (laufen automatisch vor jedem Commit/Push):
- **ruff** — Lint + Format
- **pytest-cov** — Tests + Coverage ≥80%
- **branch-name** — Convention `(feature|hotfix|chore|release)/<name>-<num>-<desc>`

---

## 🏢 Stack

| Komponente | Technologie |
|-----------|------------|
| API | FastAPI 0.115 |
| Queue | SQLite (WAL-Modus) |
| TTS Primary | ElevenLabs `eleven_multilingual_v2` |
| TTS Fallback | Azure TTS / Amazon Polly (Stubs) |
| Storage | Lokales Filesystem + Caddy (static /audio) |
| Worker | Python polling worker (sqlite queue) |
| Container | Docker + Compose |
| Tests | pytest + pytest-cov + respx |
| Lint | ruff |

---

## 📁 Projektstruktur

```
tts-service/
├── app/
│   ├── api/          # FastAPI Routes (synthesize, jobs, admin)
│   ├── backends/     # TTS Backend Implementierungen
│   ├── db/           # SQLite Schema + CRUD
│   ├── middleware/   # Auth Middleware
│   ├── storage/      # Local File Storage
│   └── worker/       # Job Queue + Worker Loop + Webhook
├── tests/            # pytest Tests (≥80% Coverage)
├── architecture/     # Architektur-Dokumentation
├── tasks/todo/       # Task-Definitionen (TTS-A1 bis TTS-H2)
├── config.yaml       # Default-Konfiguration
├── .env.example      # Secrets-Template
├── Dockerfile        # Multi-stage Build
└── docker-compose.yml
```

---

## 📖 Docs

- [`architecture/ARCHITECTURE.md`](architecture/ARCHITECTURE.md) — Vollständige Architektur & Designentscheidungen
- [`docs/research.md`](docs/research.md) — Provider-Vergleich, Kosten, Self-Hosted-Optionen
- [`.env.example`](.env.example) — Alle Konfigurationsoptionen mit Beschreibungen

---

*Built with 🤖 + ☕ by beisel-it*

## 📦 Deployment

- Local E2E stack: `docker-compose.yml` (includes Caddy on :8080, API on :8081)
- Production stack: `docker-compose.production.yml` (pulls GHCR images, Caddy on :80/:443)
- Container images (CI): `ghcr.io/beisel-it/tts-service/tts-service-api` and `.../tts-service-worker`

Consumer guide: [`docs/CONSUMER_IMPLEMENTATION_GUIDE.md`](docs/CONSUMER_IMPLEMENTATION_GUIDE.md)
