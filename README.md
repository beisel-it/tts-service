# tts-service

Asynchroner TTS-Webservice für deutsche Sprachsynthese.

Text rein → Job-ID + Audio-URL zurück → Audio erscheint dort wenn fertig.  
Wir sind kein CDN — wir synthetisieren einmal, Consumer cached selbst.

## Docs

- `architecture/ARCHITECTURE.md` — Vollständige Architektur & Designentscheidungen
- `docs/research.md` — Provider-Vergleich, Kosten, Self-Hosted-Optionen

## Tasks

Tasks liegen in `tasks/todo/`. Shortcodes: TTS-A1 bis TTS-H2.  
Parallelisierbar nach Gruppen: A (Foundation) → B/C/D/F parallel → E/G/H.

## Stack

- FastAPI + Python 3.12
- SQLite (Jobs + Queue)
- ElevenLabs API (eleven_multilingual_v2)
- Lokales Filesystem + Nginx für Audio-Serving
- Docker Compose
