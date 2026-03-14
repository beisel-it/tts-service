# Task: Worker-Loop
Shortcode: TTS-C2
Stage: todo
Status: todo
Priority: P1
Definition of Done:
- Polling-Loop: claim_next_job → Backend aufrufen → Storage schreiben → complete/fail
- Graceful shutdown on SIGTERM
- Retry-Logik: max 3 Versuche, dann permanent failed
- Logging: Job-ID, Backend, Chars, Dauer
Depends on: TTS-C1, TTS-D1, TTS-A3
