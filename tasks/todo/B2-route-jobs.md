# Task: GET /jobs/{id} Route
Shortcode: TTS-B2
Stage: todo
Status: todo
Priority: P2
Definition of Done:
- Gibt vollständigen Job-Record zurück (alle Felder aus Schema)
- 404 wenn Job nicht existiert
Depends on: TTS-A2

---

## Research & Reference

### Key Patterns

- **FastAPI Path Parameter + HTTPException:** `@router.get("/jobs/{job_id}")` → `get_job_by_id(job_id)` → wenn None: `raise HTTPException(status_code=404, detail="Job not found")`. Standard FastAPI Pattern.
- **Response Model als Pydantic BaseModel:** Definiert exakt was zurückgegeben wird — verhindert versehentliches Leaken interner Felder. Alle Felder aus ARCHITECTURE.md §3.2 als Pflichtfelder modellieren, nullable Felder als `Optional[...]`.
- **Kein Caching auf dieser Route nötig:** DB-Query auf Primary Key (`id`) mit Index ist ~0.1ms bei SQLite. Bei diesem Volumen (einige hundert Jobs/Monat) keine Optimierung notwendig. Polling-Interval liegt Consumer-seitig, nicht serverseitig.
- **Status als String im Response:** `"pending" | "processing" | "done" | "failed"` — Consumer kann damit if/else bauen. Kein Enum-Objekt im JSON, nur der String.

### Open Questions / Decisions

- **Sensible Felder exposieren?** `webhook_url` im Response zurückgeben? → Wahrscheinlich ja — Consumer hat es selbst geschickt, kein Security-Problem. Aber kann weggelassen werden um Response schlanker zu halten.
- **`error` Feld bei done-Jobs:** Wenn Job failed und dann nochmal submitted wird (idempotency), zeigt der neue Job den error des alten? → Nein, neuer Job hat eigene ID. Eindeutig.
- **Polling-Empfehlung im Response:** Soll der Response einen `Retry-After` Header oder `next_poll_url` haben? → Nice-to-have, kein MVP-Requirement.

### Reference Links

- [Response schema]: ARCHITECTURE.md §3.2
- [FastAPI HTTPException]: https://fastapi.tiangolo.com/tutorial/handling-errors/
- [FastAPI Response Models]: https://fastapi.tiangolo.com/tutorial/response-model/
