# Task: docker-compose.yml
Shortcode: TTS-G2
Stage: todo
Status: todo
Priority: P2
Definition of Done:
- Services: api, worker
- Shared Volume: /data (SQLite + Audio-Files)
- env_file: .env
- Restart-Policy: unless-stopped
- Worker skalierbar (replicas kommentiert)
Depends on: TTS-G1
