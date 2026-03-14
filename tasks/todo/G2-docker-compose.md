# Task: docker-compose.yml
Shortcode: TTS-G2
Stage: todo
Status: ready for research
Priority: P2

## Definition of Done

- [x] Services defined: `api` and `worker`
- [x] Shared volume `/data` (SQLite DB + audio files)
- [x] env_file: `.env` (sourced, not hardcoded)
- [x] Restart policy: `unless-stopped`
- [x] Worker service scalable (replicas: 1, but commented for easy scale-up)
- [x] API exposed on port 8080 (localhost:8080)
- [x] Health check on API service
- [x] Worker service has CPU/Memory limits (optional, but recommended)
- [x] Compose file validates with `docker-compose config`
- [x] Services start, communicate via service name, and stop gracefully

## Steps

1. **File Structure**
   - Create `docker-compose.yml` at project root
   - Ensure `.env.example` exists as template (separate task or document reference)

2. **Services Definition: api**
   ```yaml
   api:
     build:
       context: .
       dockerfile: Dockerfile
     container_name: tts-api
     ports:
       - "8080:8080"
     volumes:
       - tts-data:/data
       - ./config.yaml:/app/config.yaml:ro
     env_file: .env
     environment:
       - LOG_LEVEL=info
     restart: unless-stopped
     healthcheck:
       test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
       interval: 30s
       timeout: 3s
       retries: 3
       start_period: 10s
     depends_on:
       - worker  # Optional: signals startup order (not strict)
   ```

3. **Services Definition: worker**
   ```yaml
   worker:
     build:
       context: .
       dockerfile: Dockerfile
     container_name: tts-worker
     command: worker  # Override default 'api' CMD
     volumes:
       - tts-data:/data
       - ./config.yaml:/app/config.yaml:ro
     env_file: .env
     environment:
       - LOG_LEVEL=info
     restart: unless-stopped
     # For horizontal scaling (manual or via swarm):
     # deploy:
     #   replicas: 3
   ```

4. **Shared Volume**
   - Define named volume `tts-data`:
     ```yaml
     volumes:
       tts-data:
         driver: local
         driver_opts:
           type: none
           o: bind
           device: ./data  # Local ./data directory
     ```
   - Purpose: Shared SQLite DB (`/data/jobs.db`) + Audio files (`/data/audio/`)

5. **env_file Configuration**
   - Reference `.env` (via `env_file: .env`)
   - Create `.env.example` with placeholders:
     ```
     TTS_SERVICE_API_KEY=your-api-key-here
     ELEVENLABS_API_KEY=your-elevenlabs-key-here
     WEBHOOK_SIGNING_SECRET=your-secret-here
     LOG_LEVEL=info
     WORKER_CONCURRENCY=3
     ```
   - Document: users copy `.env.example` → `.env` and fill in values

6. **Network**
   - Default bridge network is sufficient
   - Services communicate via hostname (e.g., `http://api:8080/health`)
   - Explicit network definition not needed for this simple setup

7. **Restart Policy**
   - Use `unless-stopped` (survives docker daemon restart, respects manual stop)
   - API and Worker both get same policy (both critical)

8. **Limits & Resources (Optional but Recommended)**
   - Add to both services:
     ```yaml
     deploy:
       resources:
         limits:
           cpus: '1.0'
           memory: 512M
         reservations:
           cpus: '0.5'
           memory: 256M
     ```
   - Prevents runaway resource usage

9. **Logging**
   - Default Docker logging driver is fine
   - Optional: add logging driver config if structured logs needed later

10. **Validation**
    - Run: `docker-compose config` (parses & validates syntax)
    - Run: `docker-compose up` (starts both services)
    - Test API: `curl http://localhost:8080/health`
    - Verify worker is running: `docker-compose ps` should show both healthy

## Blocking

- **TTS-G1 (Dockerfile)** must be complete and tested before building compose file
  - Reason: G2 builds the image defined in TTS-G1

## Dependencies

- TTS-G1: Dockerfile (must exist, must build successfully)
- All services in architecture (A1–E1) must have stubs or implementations for `/health` to work

## Notes

- **Data Persistence:** `tts-data` volume binds to local `./data/` directory. Ensure directory exists: `mkdir -p ./data`
- **Configuration:** Both API and Worker share `config.yaml`. Mounted as read-only to prevent accidental changes in container.
- **Scaling:** Worker is stateless. To scale: uncomment `deploy.replicas: N` or use `docker-compose up --scale worker=3`
- **Logs:** View with `docker-compose logs -f [service]`
- **Cleanup:** `docker-compose down -v` removes containers and volumes (careful!)

## Example Startup Checklist

1. Copy `.env.example` → `.env` and fill in API keys
2. Run `mkdir -p ./data` (create volume mount point)
3. Run `docker-compose config` (validate)
4. Run `docker-compose up` (start)
5. Wait 10s for health checks
6. Curl `http://localhost:8080/health` → should return `{"status": "ok"}`
7. Check logs: `docker-compose logs -f api` / `docker-compose logs -f worker`

---

## Research & Reference

### Key Patterns

- **Named Volume mit bind-mount:** `driver_opts: type: none, o: bind, device: ./data` — bindet `./data/` auf dem Host als named volume. Vorteil: `docker-compose down -v` löscht den Named Volume Record, aber `./data/` bleibt auf dem Host erhalten. Daten überleben `down -v`. Alternativ: simpler bind-mount `- ./data:/data` direkt im service — klarer, kein Volume-Trick nötig.
- **`depends_on` mit health check:** `depends_on: worker: condition: service_healthy` — wartet bis Worker healthy ist bevor API startet. Aber: Worker hat keinen Health-Endpoint. → `depends_on` ohne condition weglassen oder nur als Startup-Order-Hint nutzen. API und Worker sind unabhängig.
- **Graceful Stop Timeout:** Docker Compose sendet SIGTERM, wartet `stop_grace_period` (default 10s), dann SIGKILL. Für Worker der einen Job zu Ende bringen muss: `stop_grace_period: 30s` setzen. Sicherstellen dass ElevenLabs-Call in <30s fertig ist.
- **Shared Volume für SQLite:** Beide Container (api + worker) greifen auf dieselbe `/data/jobs.db` zu. WAL-Mode (aus A2) erlaubt das sicher. Wichtig: beide Container müssen denselben User-UID haben der auf `/data/` schreibt — sichergestellt durch Dockerfile (uid 1000) + Volume-Permissions.
- **`env_file` vs `environment`:** `env_file: .env` lädt alle Vars aus `.env`. `environment:` überschreibt einzelne Vars. Beides kombinieren möglich: `env_file` für Secrets, `environment` für non-secrets die direkt sichtbar sein sollen.

### Open Questions / Decisions

- **`docker-compose.yml` Version:** `version: "3.8"` oder kein `version` key? Ab Compose V2 (docker compose, ohne Bindestrich) ist `version` deprecated. → Kein `version` key — moderner Standard.
- **Worker `depends_on` API?** Worker braucht die API nicht — Worker liest direkt aus SQLite. Kein `depends_on` zwischen beiden Services nötig. Beide starten unabhängig.
- **Ressource-Limits:** `deploy.resources` funktioniert in Compose-Standalone nur mit `docker compose` (nicht `docker-compose` v1). Bei Hetzner CX22 (2 vCPU, 4 GB): Limits optional aber empfohlen. `cpus: "0.5"`, `memory: 256M` pro Service = 1 vCPU + 512 MB für beide zusammen. Realistisch bei diesem Workload.

### Reference Links

- [Docker Compose reference]: https://docs.docker.com/compose/compose-file/
- [Named volumes vs bind mounts]: https://docs.docker.com/storage/volumes/
- [stop_grace_period]: https://docs.docker.com/compose/compose-file/05-services/#stop_grace_period
- [WAL-Mode für Multiprocess SQLite]: C1-job-queue.md (Research §WAL-Mode)
- [Deployment config]: ARCHITECTURE.md §9
