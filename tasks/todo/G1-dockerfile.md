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

---

## Research & Reference

### Key Patterns

- **`python:3.12-slim` auf ARM64:** `slim` = Debian bookworm-slim, kein Alpine (Alpine hat musl statt glibc — Kompatibilitätsprobleme mit einigen Python-Packages). Auf Hetzner ARM64 (aarch64): `python:3.12-slim` pulled automatisch das richtige Image für die Plattform. Kein `--platform` Flag nötig wenn auf ARM-Host gebaut wird.
- **Non-root User:** `RUN addgroup --system app && adduser --system --ingroup app app` (Debian-Stil). Dann `USER app`. `/data`-Volume: `RUN mkdir -p /data && chown app:app /data` **vor** `USER app`.
- **Layer-Caching optimieren:** `COPY requirements.txt .` → `RUN pip install ...` → `COPY app/ .` — Requirements als eigener Layer cacht die pip-Installation solange sich requirements.txt nicht ändert. Häufigste Optimierung die vergessen wird.
- **Entrypoint Script:** `ENTRYPOINT ["/app/docker-entrypoint.sh"]` + `CMD ["api"]` — exec-Form (JSON-Array), nicht Shell-Form. Wichtig für Graceful Shutdown: exec-Form macht das Script selbst zu PID 1, Signal geht direkt ans Script. Shell-Form wrappet in `/bin/sh -c`, SIGTERM landet beim Shell-Prozess nicht beim Python-Prozess.
- **HEALTHCHECK:** Docker-native Health-Check mit curl. Voraussetzung: `curl` im Image installiert. Alternative: `wget -q --spider` (busybox wget, falls curl zu groß). Bei `python:3.12-slim`: curl via apt installieren, ~2MB.
- **`.dockerignore`:** Verhindert dass `data/`, `*.db`, `.env`, Tests in den Build-Context kommen. Spart Bau-Zeit und verhindert versehentliches Einbetten von Secrets.

### Open Questions / Decisions

- **`pip install` als root oder als app-user?** Besser als root installieren (system-weit), dann zu app-user wechseln. Alternativ: `pip install --user` als app-user + PATH anpassen. → Empfehlung: pip als root (default), dann `USER app`. Simpler.
- **`config.yaml` im Image oder nur als Volume?** Im DoD: `config.yaml` wird als read-only Volume gemountet. Dockerfile kopiert also kein config.yaml. Was ist der Default wenn kein Volume? → Entweder: `config.yaml.example` ins Image kopieren, oder App schlägt beim Start fehl mit klarer Fehlermeldung. Entscheidung dokumentieren.
- **`COPY tests/` ins Image?** Nein — für Production-Image nicht nötig. `.dockerignore` schließt `tests/` aus.

### Reference Links

- [Docker best practices (non-root)]: https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#user
- [Python Docker best practices]: https://testdriven.io/blog/docker-best-practices/
- [exec vs shell form ENTRYPOINT]: https://docs.docker.com/reference/dockerfile/#entrypoint
- [HEALTHCHECK]: https://docs.docker.com/reference/dockerfile/#healthcheck
- [ARM64 + python:slim]: https://hub.docker.com/_/python (multi-arch tags)
- [Deployment config]: ARCHITECTURE.md §9
