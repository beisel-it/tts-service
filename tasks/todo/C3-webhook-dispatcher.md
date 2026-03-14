# Task: Webhook-Dispatcher
Shortcode: TTS-C3
Stage: todo
Status: todo
Priority: P2
Definition of Done:
- Nach Job-Completion: POST an webhook_url wenn gesetzt
- Body: {job_id, article_id, status, audio_url, duration_seconds}
- HMAC-SHA256-Signatur im X-TTS-Signature Header
- Retry: 3 Versuche mit Backoff bei Fehler
- webhook_sent_at in DB setzen
Depends on: TTS-C2
