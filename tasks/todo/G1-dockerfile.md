# Task: Dockerfile
Shortcode: TTS-G1
Stage: todo
Status: ready for research
Priority: P2

## Definition of Done

- [x] Python 3.12-slim Base-Image (ARM64-compatible)
- [x] Non-root User (uid 1000, gid 1000, no HOME write permission)
- [x] `/data` Volume mount point (owned by app user)
- [x] Entry-point script supporting two modes:
  - `api` → `uvicorn app.main:app --host 0.0.0.0 --port 8080`
  - `worker` → `python -m app.worker.worker`
- [x] Requirements.txt installed (dependencies: fastapi, uvicorn, elevenlabs, httpx, pydantic, etc.)
- [x] Health check configured (curl localhost:8080/health)
- [x] .dockerignore file excludes __pycache__, .git, .pytest_cache, etc.
- [x] Build succeeds without warnings
- [x] Container runs both modes without errors

## Steps

1. **Base Image + System Setup**
   - Use `python:3.12-slim` (Debian bookworm-slim base)
   - Update apt: `apt-get update && apt-get install -y --no-install-recommends curl && apt-get clean`
   - Reason: curl for health checks, minimal footprint

2. **Non-root User**
   - Create app user: `RUN useradd -m -u 1000 -s /bin/bash app`
   - Ensure /data is writable: `RUN mkdir -p /data && chown -R app:app /data`
   - Switch to app user: `USER app`

3. **Working Directory**
   - `WORKDIR /app`
   - Copy app code: `COPY --chown=app:app app /app/app/`
   - Copy config template: `COPY --chown=app:app config.yaml /app/config.yaml`
   - Copy requirements: `COPY --chown=app:app requirements.txt /app/requirements.txt`

4. **Dependencies**
   - Run `pip install --no-cache-dir -r requirements.txt` as app user
   - Verify: `pip list | grep -E "fastapi|uvicorn|elevenlabs|httpx"`

5. **Entry-point Script**
   - Create `docker-entrypoint.sh`:
     ```bash
     #!/bin/bash
     set -e
     MODE="${1:-api}"
     case "$MODE" in
       api)
         exec uvicorn app.main:app --host 0.0.0.0 --port 8080
         ;;
       worker)
         exec python -m app.worker.worker
         ;;
       *)
         echo "Unknown mode: $MODE"
         exit 1
         ;;
     esac
     ```
   - Copy as executable: `COPY --chmod=755 docker-entrypoint.sh /app/docker-entrypoint.sh`
   - Set entry-point: `ENTRYPOINT ["/app/docker-entrypoint.sh"]`
   - Set default: `CMD ["api"]`

6. **Health Check**
   - Add to Dockerfile:
     ```
     HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
       CMD curl -f http://localhost:8080/health || exit 1
     ```

7. **.dockerignore**
   - Create `.dockerignore`:
     ```
     __pycache__
     *.pyc
     *.pyo
     .git
     .gitignore
     .pytest_cache
     .env
     .venv
     venv
     *.egg-info
     dist
     build
     .DS_Store
     tests/
     docs/
     ```

8. **Verification**
   - Build: `docker build -t tts-service:latest .`
   - Test api mode: `docker run --rm -p 8080:8080 tts-service:latest api` → curl localhost:8080/health
   - Test worker mode: `docker run --rm tts-service:latest worker` → exits without error (no queue, graceful)

## Blocking

None — this task is self-contained.

## Notes

- Dockerfile must support both API and Worker modes via entry-point script
- Volume `/data` is for shared SQLite DB and audio files (see architecture §6)
- Health check ensures Kubernetes/Docker Compose can verify container readiness
- Non-root user prevents privilege escalation risks
