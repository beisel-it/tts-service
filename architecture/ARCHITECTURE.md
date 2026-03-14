# TTS Synthesis Service — Architecture & Implementation Document

**Version:** 1.0  
**Stand:** 2026-03-14  
**Zweck:** Ausgangslage für Task-Erzeugung und Work Planning  
**Parallelisierbarkeit:** Hoch — Module sind entkoppelt, können parallel entwickelt werden

---

## 1. Überblick & Ziel

Ein schlanker HTTP-Webservice, der Text-Inhalte asynchron in Audio synthetisiert und dem Consumer eine **permanente Datei-URL** liefert. Der Consumer ist selbst für Caching und Delivery verantwortlich.

**Kernprinzipien:**
- **Promise-URL-Modell:** Request → sofortige Job-ID + Ziel-URL → Audio erscheint dort wenn fertig
- **Wir sind kein CDN:** Audio wird einmal auf Object Storage abgelegt, URL wird einmalig kommuniziert — danach out of scope
- **Provider-Agnostisch:** Einheitliche interne Abstraktionsschicht für beliebige TTS-Backends
- **Stateless Worker:** Jobs laufen in einer Queue, horizontal skalierbar

---

## 2. Systemarchitektur

```
┌─────────────────────────────────────────────────────────────────┐
│  Consumer (Community-App)                                        │
│  POST /synthesize → job_id + audio_url (pending)                │
│  GET  /jobs/{job_id} → status polling                           │
│  ODER webhook callback wenn fertig                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────────┐
│  API Layer  (FastAPI)                                            │
│  • /synthesize    POST  — Job erzeugen                          │
│  • /jobs/{id}     GET   — Status abfragen                       │
│  • /health        GET   — Healthcheck                           │
│  • /admin/voices  GET   — Verfügbare Stimmen (je Backend)       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ enqueue
┌──────────────────────────▼──────────────────────────────────────┐
│  Job Queue  (Redis / SQLite-Queue)                               │
│  • pending → processing → done / failed                         │
│  • Job-Record: {id, text_hash, status, audio_url, backend,      │
│                 created_at, completed_at, error?}                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ consume
┌──────────────────────────▼──────────────────────────────────────┐
│  Worker  (Background-Prozess, n Instanzen)                       │
│  • Holt Job aus Queue                                            │
│  • Wählt Backend via Router                                      │
│  • Ruft TTS-Backend auf                                          │
│  • Schreibt Audio auf Object Storage                             │
│  • Markiert Job als done, triggert ggf. Webhook                  │
└─────────────┬───────────────────────────────────────────────────┘
              │
   ┌──────────▼──────────────────────────────┐
   │  Backend Router                          │
   │  Wählt Provider basierend auf Config:   │
   │  • backend: "elevenlabs" (default)       │
   │  • backend: "azure"                      │
   │  • backend: "polly"                      │
   │  • backend: "piper" (self-hosted)        │
   └──────────┬──────────────────────────────┘
              │
   ┌──────────▼────────────────┐   ┌──────────────────────────────┐
   │  ElevenLabs Backend       │   │  Object Storage               │
   │  POST /v1/text-to-speech  │   │  (Cloudflare R2 / S3)         │
   │  model: multilingual_v2   │──▶│  audio/{hash}.mp3             │
   │  voice_id: configurable   │   │  Public URL → Consumer        │
   └───────────────────────────┘   └──────────────────────────────┘
```

---

## 3. API-Spezifikation

### 3.1 Job anlegen

```
POST /synthesize
Content-Type: application/json
X-API-Key: {service_api_key}

{
  "text": "Vollständiger Artikeltext...",
  "article_id": "artikel-2026-03-14-001",    // optional, für Idempotenz
  "voice": "de-default",                      // optional, default aus Config
  "backend": "elevenlabs",                    // optional, default aus Config
  "webhook_url": "https://app.example.com/tts-callback"  // optional
}
```

```
201 Created

{
  "job_id": "tts_7f3a2b1c",
  "status": "pending",
  "audio_url": "https://r2.example.com/audio/sha256-of-text.mp3",
  "poll_url": "https://tts.service/jobs/tts_7f3a2b1c",
  "estimated_seconds": 5
}
```

**Wichtig:** `audio_url` ist die **finale, permanente URL** — sie steht schon im Response, auch wenn die Datei noch nicht existiert. Damit kann der Consumer die URL sofort in die DB schreiben und später direkt abrufen.

---

### 3.2 Job-Status abfragen (Polling)

```
GET /jobs/{job_id}
X-API-Key: {service_api_key}
```

```
200 OK

{
  "job_id": "tts_7f3a2b1c",
  "article_id": "artikel-2026-03-14-001",
  "status": "done",           // pending | processing | done | failed
  "audio_url": "https://r2.example.com/audio/sha256-of-text.mp3",
  "duration_seconds": 142,
  "chars_processed": 1840,
  "backend_used": "elevenlabs",
  "created_at": "2026-03-14T10:00:00Z",
  "completed_at": "2026-03-14T10:00:07Z",
  "error": null
}
```

---

### 3.3 Webhook Callback (wenn `webhook_url` angegeben)

Der Service sendet nach Fertigstellung einen POST an die angegebene URL:

```
POST {webhook_url}
Content-Type: application/json
X-TTS-Signature: hmac-sha256-of-body   // Consumer kann validieren

{
  "job_id": "tts_7f3a2b1c",
  "article_id": "artikel-2026-03-14-001",
  "status": "done",
  "audio_url": "https://r2.example.com/audio/sha256-of-text.mp3",
  "duration_seconds": 142
}
```

---

### 3.4 Idempotenz via article_id / text_hash

Wenn ein `article_id` bereits einen abgeschlossenen Job hat **oder** der `text`-Inhalt identisch ist (SHA-256-Hash), wird **kein neuer Job erzeugt**. Stattdessen wird der bestehende Job-Record zurückgegeben:

```
200 OK  (statt 201)
{
  "job_id": "tts_7f3a2b1c",
  "status": "done",
  "audio_url": "...",
  "cached": true
}
```

---

## 4. Backend-Abstraktionsschicht

Jedes TTS-Backend implementiert ein einheitliches Interface:

```python
class TTSBackend(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        output_format: str = "mp3_44100_128"
    ) -> bytes:
        """Gibt rohe Audio-Bytes zurück."""
        ...

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """Gibt verfügbare Stimmen zurück."""
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...
```

### 4.1 ElevenLabs Backend (Phase 1 — implementieren)

```python
class ElevenLabsBackend(TTSBackend):
    # Endpoint: POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}
    # Model: eleven_multilingual_v2
    # Output: mp3_44100_128 (128kbps MP3, ausreichend für Sprache)
    # Auth: xi-api-key Header
    # Voice Default: de-DE konfigurierbar (z.B. Adam, Rachel, oder Custom Clone)
```

### 4.2 Azure Neural TTS Backend (Phase 2 — Stub, nicht implementieren)

```python
class AzureBackend(TTSBackend):
    # Endpoint: Azure Cognitive Services Speech SDK
    # Voice: de-DE-KatjaNeural / de-DE-ConradNeural
    # Output: audio-16khz-128kbitrate-mono-mp3
    # Auth: Ocp-Apim-Subscription-Key Header
    pass  # TODO Phase 2
```

### 4.3 Amazon Polly Backend (Phase 2 — Stub)

```python
class PollyBackend(TTSBackend):
    # AWS SDK: boto3 polly.synthesize_speech()
    # Voice: Vicki (de-DE), Daniel (de-DE), Neural engine
    # Output: mp3
    pass  # TODO Phase 2
```

### 4.4 Piper Backend (Phase 2 — Stub, Self-Hosted)

```python
class PiperBackend(TTSBackend):
    # Local subprocess oder HTTP zu lokalem Piper-Service
    # Model: de_DE-thorsten-high
    # Output: WAV → konvertieren zu MP3 via ffmpeg
    pass  # TODO Phase 2
```

---

## 5. Datenbankschema (Jobs)

```sql
CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,         -- tts_{uuid8}
    article_id      TEXT,                     -- vom Consumer, optional
    text            TEXT NOT NULL,            -- Volltext (wird von Worker zur Synthese ausgelesen)
    text_hash       TEXT NOT NULL,            -- SHA-256 des Textes
    text_preview    TEXT,                     -- erste 100 Zeichen (Debugging)
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|processing|done|failed
    audio_url       TEXT NOT NULL,            -- permanente URL (schon beim Anlegen gesetzt)
    storage_key     TEXT,                     -- interner Pfad im Object Storage
    backend         TEXT,                     -- welches Backend verwendet wurde
    voice_id        TEXT,
    duration_seconds REAL,
    chars_processed INTEGER,
    webhook_url     TEXT,
    webhook_sent_at TEXT,
    error           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_jobs_text_hash ON jobs(text_hash);
CREATE INDEX idx_jobs_article_id ON jobs(article_id);
CREATE INDEX idx_jobs_status ON jobs(status);
```

---

## 6. Storage

**Lokales Filesystem — kein externer Storage-Service.**

Audio-Files liegen auf dem Server, werden über den eigenen Service (oder Nginx direkt) ausgeliefert. Der Consumer holt die Datei ab — danach wird sie irgendwann aufgeräumt.

**Dateinamen-Schema:**
```
/data/audio/{text_hash[:8]}/{text_hash}.mp3
```
Beispiel: `/data/audio/a3f7b2c1/a3f7b2c1...f9.mp3`

**Auslieferung:**
- Nginx `location /audio/` → `alias /data/audio/` — statisches File-Serving, kein App-Code beteiligt
- Die `audio_url` im Response zeigt auf `https://tts.service/audio/{hash}.mp3`

**Cleanup:**
- Datei gilt als "abgeholt" wenn Consumer Job-Status `done` abgefragt hat **oder** Webhook erfolgreich zugestellt wurde
- Cleanup-Job läuft periodisch (Cron oder Worker-Nebenaufgabe): löscht Files die älter als N Tage sind (konfigurierbar, Default: 7 Tage)
- Kein sofortiges Löschen — Consumer kann nochmal abrufen falls nötig

**Speicherbedarf:** ~380k Z/Monat ≈ ~30h Audio ≈ ~800 MB MP3/Monat. Hetzner CX22 hat 40 GB Disk — bei 7-Tage-Retention liegen maximal ~200 MB rum. Kein Thema.

---

## 7. Konfiguration

```yaml
# config.yaml
service:
  api_key: "${TTS_SERVICE_API_KEY}"
  host: "0.0.0.0"
  port: 8080
  worker_concurrency: 3

default_backend: "elevenlabs"

backends:
  elevenlabs:
    api_key: "${ELEVENLABS_API_KEY}"
    default_voice_id: "XB0fDUnXU5powFXDhCwa"  # Charlotte (de-fähig)
    model_id: "eleven_multilingual_v2"
    output_format: "mp3_44100_128"

  azure:
    enabled: false
    subscription_key: "${AZURE_SPEECH_KEY}"
    region: "westeurope"
    default_voice: "de-DE-KatjaNeural"

  polly:
    enabled: false
    region: "eu-central-1"
    default_voice: "Vicki"

  piper:
    enabled: false
    model_path: "/models/de_DE-thorsten-high.onnx"

storage:
  path: "/data/audio"
  public_base_url: "https://tts.service/audio"
  cleanup_after_days: 7

queue:
  backend: "sqlite"        # sqlite | redis
  sqlite_path: "/data/jobs.db"

webhook:
  signing_secret: "${WEBHOOK_SIGNING_SECRET}"
  timeout_seconds: 10
  retry_attempts: 3
```

---

## 8. Projektstruktur

```
tts-service/
├── docker-compose.yml
├── Dockerfile
├── config.yaml
├── requirements.txt
│
├── app/
│   ├── main.py                  # FastAPI App, Router-Registrierung
│   ├── config.py                # Config-Loader (Pydantic Settings)
│   ├── models.py                # DB-Schemas (SQLModel / SQLite)
│   │
│   ├── api/
│   │   ├── routes_synthesize.py # POST /synthesize
│   │   ├── routes_jobs.py       # GET /jobs/{id}
│   │   └── routes_admin.py      # GET /health, /admin/voices
│   │
│   ├── backends/
│   │   ├── base.py              # TTSBackend ABC + VoiceInfo dataclass
│   │   ├── elevenlabs.py        # ElevenLabs-Implementierung (Phase 1)
│   │   ├── azure.py             # Stub (Phase 2)
│   │   ├── polly.py             # Stub (Phase 2)
│   │   └── piper.py             # Stub (Phase 2)
│   │
│   ├── worker/
│   │   ├── queue.py             # Job-Queue (SQLite-basiert)
│   │   ├── worker.py            # Worker-Loop
│   │   └── webhook.py           # Webhook-Dispatcher
│   │
│   └── storage/
│       └── local.py             # Lokales Filesystem + Cleanup-Job
│
└── tests/
    ├── test_api.py
    ├── test_elevenlabs_backend.py
    └── test_worker.py
```

---

## 9. Deployment

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
      - ./config.yaml:/app/config.yaml:ro
    env_file: .env
    command: uvicorn app.main:app --host 0.0.0.0 --port 8080

  worker:
    build: .
    volumes:
      - ./data:/data
      - ./config.yaml:/app/config.yaml:ro
    env_file: .env
    command: python -m app.worker.worker
    # Skalierbar: deploy.replicas: 3
```

**Infrastruktur:** Hetzner CX22 (ARM64, 2 vCPU, 4 GB RAM, ~€4,50/Mo)  
Reverse Proxy: Caddy oder Nginx, HTTPS via Let's Encrypt

---

## 10. Task-Übersicht (für Work Planning)

Die folgenden Aufgaben sind weitgehend unabhängig voneinander und können parallelisiert werden.

### Gruppe A — Foundation
- `A1` Config-System implementieren (Pydantic Settings, config.yaml laden)
- `A2` Datenbankschema anlegen (SQLite, SQLModel), CRUD-Operationen für Jobs
- `A3` Lokales Storage-Modul: Verzeichnis-Handling, File-Write, Public-URL-Generierung, Cleanup-Job

### Gruppe B — API Layer (depends on A1, A2)
- `B1` `POST /synthesize` — Job anlegen, Idempotenz-Check (text_hash + article_id), 201-Response mit audio_url
- `B2` `GET /jobs/{id}` — Status-Abfrage
- `B3` `GET /health` + `GET /admin/voices`
- `B4` API-Key-Auth Middleware

### Gruppe C — Worker (depends on A1, A2)
- `C1` Job-Queue-Implementierung (SQLite polling loop, Status-Transitions)
- `C2` Worker-Loop: Job holen → Backend aufrufen → Storage schreiben → Job done/failed
- `C3` Webhook-Dispatcher: HTTP-POST nach Completion, HMAC-Signatur, Retry-Logik

### Gruppe D — ElevenLabs Backend (depends on A1)
- `D1` ElevenLabs Backend: `synthesize()` via REST API
- `D2` ElevenLabs Backend: `list_voices()` — verfügbare Stimmen abrufen
- `D3` Error-Handling: Rate Limits, Auth-Fehler, Retry mit Backoff

### Gruppe E — Storage-Anbindung (depends on A3, D1)
- `E1` Worker + R2 Integration: Audio-Bytes von Backend → Upload → URL

### Gruppe F — Backend Stubs (depends on A1)
- `F1` Azure Backend Stub (Interface implementiert, raises NotImplementedError)
- `F2` Polly Backend Stub
- `F3` Piper Backend Stub

### Gruppe G — Deployment
- `G1` Dockerfile (Python 3.12-slim, non-root)
- `G2` docker-compose.yml (api + worker)
- `G3` Caddy/Nginx Config + HTTPS
- `G4` `.env`-Template, Secrets-Dokumentation

### Gruppe H — Tests
- `H1` API-Tests: `/synthesize`, `/jobs/{id}` (pytest + httpx)
- `H2` ElevenLabs Backend-Tests (gemockt)
- `H3` Worker-Integrationstests

---

## 11. Nicht im Scope (bewusste Entscheidungen)

| Was | Warum nicht |
|---|---|
| Externer Object Storage (R2/S3) | Lokales FS + Nginx reicht, kein weiterer Service nötig |
| CDN / Audio-Proxy | Consumer cached selbst, wie bisher |
| Streaming TTS | Statische Artikel — Pre-render reicht |
| UI / Dashboard | CLI + logs ausreichend, optional später |
| Multi-Tenancy | Single-Consumer-Service |
| Audio-Format-Konvertierung | MP3 128kbps ist Standard, kein Bedarf |
| Löschen von Audio-Files | Hash-basiert, günstiger als Verwaltungsaufwand |
