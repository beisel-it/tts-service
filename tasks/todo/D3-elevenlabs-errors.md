# Task: ElevenLabs Error-Handling + Retry
Shortcode: TTS-D3
Stage: todo
Status: todo
Priority: P2
Definition of Done:
- 429 Rate Limit: Retry-After respektieren, exponentieller Backoff
- 401/403: sofort failed, klare Fehlermeldung
- Netzwerkfehler: bis zu 3 Retries
- Alle Fehler als spezifische Exceptions (ElevenLabsRateLimitError etc.)
Depends on: TTS-D1
