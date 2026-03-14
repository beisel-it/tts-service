# Task: POST /synthesize Route
Shortcode: TTS-B1
Stage: todo
Status: todo
Priority: P1
Definition of Done:
- Nimmt {text, article_id?, voice?, backend?, webhook_url?}
- Berechnet text_hash (SHA-256)
- Idempotenz-Check: article_id oder text_hash bereits done? → 200 + cached:true
- Neuer Job: audio_url deterministisch berechnen, Job in DB anlegen, in Queue stellen
- Response: 201 mit job_id, status, audio_url, poll_url
Depends on: TTS-A1, TTS-A2

---

## Research & Reference

### Key Patterns

- **SHA-256 Text-Hash:** `hashlib.sha256(text.encode('utf-8')).hexdigest()` — deterministisch, kollisionsresistent. Wichtig: Text normalisieren vor dem Hashing (strip whitespace, normalize unicode?) — Entscheidung treffen und dokumentieren. Einfachstes sicheres Default: `text.strip()` vor dem Hash.
- **Zwei-Level Idempotenz:** (1) `article_id`-Check zuerst — wenn vorhanden und Job done, direkt zurückgeben. (2) `text_hash`-Check als Fallback — gleicher Inhalt, andere oder keine article_id. Reihenfolge wichtig: article_id ist "business identity", text_hash ist "content identity".
- **Promise URL sofort berechnen:** `audio_url = storage.get_audio_url(text_hash)` — kein I/O, reine String-Berechnung. URL steht im Response bevor der Worker überhaupt startet. Consumer kann URL sofort persistieren.
- **201 vs 200 für Idempotenz:** Neuer Job → `status_code=201`, `cached=False`. Existing Job → `status_code=200`, `cached=True`. FastAPI: `@router.post("/synthesize", status_code=201)` — der Cache-Hit kann mit `Response` object den Status auf 200 überschreiben.
- **FastAPI Request Body mit Pydantic:** `class SynthesizeRequest(BaseModel): text: str; article_id: str | None = None; ...` — automatische Validierung. `text` min_length=1 setzen.
- **Background Tasks vs Queue:** Wir nutzen die SQLite Queue (C1), keine FastAPI BackgroundTasks. Route schreibt Job in DB und gibt sofort 201 zurück. Worker-Prozess läuft separat.

### Open Questions / Decisions

- **Text-Normalisierung vor Hash:** Soll `text.strip()` reichen, oder auch `unicodedata.normalize('NFC', text)`? → Empfehlung: `text.strip()` für MVP. Unicode-Normalisierung wenn Probleme auftreten.
- **`text` im Job-Record speichern (ENTSCHIEDEN):** Consumer POST-Body enthält `text` — dieser wird vollständig in `jobs.text` (TEXT NOT NULL) gespeichert. ARCHITECTURE.md §5 enthält das Feld. Route B1 ist verantwortlich für Schreiben; Worker C2 liest `job.text` zur Synthese. Kein separates Lookup nötig.
- **Maximale Text-Länge:** ElevenLabs limitiert auf 5000 Zeichen pro Request. Längere Texte → Error oder Chunking? → MVP: 422 zurückgeben mit klarer Fehlermeldung wenn text > 5000 Zeichen.
- **`estimated_seconds` im Response:** Woher? Einfachster Weg: `len(text) / 15` (ca. 15 Zeichen/Sekunde Synthesezeit als Heuristik). Oder weglassen und `null` zurückgeben.

### Reference Links

- [Idempotency pattern]: ARCHITECTURE.md §3.4
- [Promise URL concept]: ARCHITECTURE.md §1 + §3.1
- [Job schema]: ARCHITECTURE.md §5
- [FastAPI status codes]: https://fastapi.tiangolo.com/tutorial/response-status-code/
- [ElevenLabs char limit]: https://elevenlabs.io/docs/api-reference/text-to-speech/convert (5000 chars/request)
- [hashlib Python docs]: https://docs.python.org/3/library/hashlib.html
