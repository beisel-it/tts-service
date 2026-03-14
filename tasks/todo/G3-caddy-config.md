# Task: Caddyfile + Reverse Proxy + HTTPS
Shortcode: TTS-G3
Stage: todo
Status: refined → ready for research
Priority: P2
Owner: _unassigned_

---

## Decision

We use **Caddy** (not Nginx) for TLS termination + reverse proxy.
Reason: simpler config, automatic HTTPS via Let's Encrypt, fewer moving parts.

---

## Definition of Done (testable)

- [ ] Caddy config template added to repo: `caddy/Caddyfile`
- [ ] Reverse proxy routing: `/ → localhost:8080` (API), responds with 200 on `/health`
- [ ] Static file serving: `/audio/*` serves files from `/data/audio/` (no directory listing)
- [ ] HTTPS enabled: automatic Let's Encrypt (default), TLS 1.2+
- [ ] HTTP redirect: all `http://` → `https://`
- [ ] Compression enabled for JSON responses (API) (Caddy defaults are fine; document behavior)
- [ ] Cache headers for `/audio/*`: `Cache-Control: public, max-age=604800` (7 days)
- [ ] No cache for `/health`, `/synthesize`, `/jobs/*`: `Cache-Control: no-cache`
- [ ] Security headers set (minimum): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- [ ] Tested: `curl https://tts.service/health` returns `{"status":"ok"}`
- [ ] Tested: `curl -I https://tts.service/audio/<hash>.mp3` serves file or 404 correctly
- [ ] Caddy config validated: `caddy validate --config caddy/Caddyfile`
- [ ] Restart/reload documented and tested

---

## Steps

### Phase 1: Template
1. Create `caddy/Caddyfile` in repo.
2. Use site label `tts.service` (or `${TTS_DOMAIN}` as env-var in deployment docs).

### Phase 2: Routing
3. Reverse proxy:
   - `reverse_proxy localhost:8080`
4. Static audio:
   - `handle_path /audio/* { root * /data/audio; file_server }`
   - Ensure path matches the storage URL scheme: `.../audio/<prefix>/<hash>.mp3`

### Phase 3: Headers / Caching
5. Add cache headers for audio:
   - `header /audio/* Cache-Control "public, max-age=604800"`
6. Disable caching for API endpoints:
   - `header /health Cache-Control "no-cache"`
   - `header /synthesize Cache-Control "no-cache"`
   - `header /jobs/* Cache-Control "no-cache"`
7. Security headers:
   - `header X-Content-Type-Options "nosniff"`
   - `header X-Frame-Options "DENY"`

### Phase 4: TLS
8. Let Caddy manage certs automatically.
9. Document where Caddy stores certs and how to troubleshoot ACME.

### Phase 5: Testing
10. Validate config: `caddy validate --config caddy/Caddyfile`
11. Run Caddy and test:
    - `curl https://tts.service/health`
    - `curl -I https://tts.service/audio/<hash>.mp3`

---

## Blocking

- Requires: **API running on localhost:8080** (G1-G2 must be implemented first)
- Requires: **domain name registered + DNS pointing to server IP**
- Requires: **/data/audio/** exists (task A3)
- Requires: Caddy installed on host

---

## Notes

### Minimal Caddyfile Sketch

```caddyfile
{
  # optional global options
}

tts.service {
  encode zstd gzip

  handle_path /audio/* {
    root * /data/audio
    file_server
    header Cache-Control "public, max-age=604800"
  }

  handle {
    reverse_proxy localhost:8080
  }

  header {
    X-Content-Type-Options "nosniff"
    X-Frame-Options "DENY"
  }

  header /health Cache-Control "no-cache"
  header /synthesize Cache-Control "no-cache"
  header /jobs/* Cache-Control "no-cache"
}
```

---

## Related Tasks
- A3 (Storage setup)
- G2 (Docker + compose)
- G4 (.env template)

---

## References
- Caddy docs: https://caddyserver.com/docs/
- Caddyfile directives: https://caddyserver.com/docs/caddyfile
