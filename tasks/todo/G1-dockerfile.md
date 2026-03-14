# Task: Dockerfile
Shortcode: TTS-G1
Stage: todo
Status: todo
Priority: P2
Definition of Done:
- Python 3.12-slim Base-Image
- Non-root User
- /data als Volume-Mount-Point
- Beide Entry-Points: api (uvicorn) und worker (python -m app.worker.worker)
