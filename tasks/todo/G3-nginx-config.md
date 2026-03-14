# Task: (DEPRECATED) Nginx-Config (superseded by Caddy)
Shortcode: TTS-G3
Stage: todo
Status: deprecated (use tasks/todo/G3-caddy-config.md)
Priority: P2
Owner: _unassigned_

---

## Definition of Done (testable)

- [ ] Nginx config file created: `/etc/nginx/sites-available/tts-service` (or template in repo)
- [ ] Reverse proxy routing: `/ → localhost:8080` (API), responds with 200 on `/health`
- [ ] Static file serving: `/audio/ → /data/audio/` (alias directive), directory-listing OFF
- [ ] HTTPS enabled: TLS 1.2+, certificate via Certbot + Let's Encrypt (or self-signed for dev)
- [ ] HTTP redirect: all `http://` → `https://` (301 permanent)
- [ ] Gzip compression enabled for JSON responses (api)
- [ ] Cache headers set for `/audio/*`: `Cache-Control: public, max-age=604800` (7 days)
- [ ] No cache for `/health`, `/synthesize`, `/jobs/*`: `Cache-Control: no-cache`
- [ ] Certbot renewal: cron job or systemd timer configured
- [ ] Tested: `curl https://tts.service/health` returns `{"status": "ok"}`
- [ ] Tested: `curl https://tts.service/audio/test-hash.mp3` serves file or 404 correctly
- [ ] Nginx syntax validation: `nginx -t` passes
- [ ] Nginx reload/restart documented and tested

---

## Steps

### Phase 1: Foundation
1. Create `nginx/tts-service.conf` in repo (template, not `/etc/nginx/`)
2. Define upstream: `upstream tts_api { server localhost:8080; }`
3. Server block for HTTP (port 80): redirect-only
4. Server block for HTTPS (port 443): main logic
5. Include TLS directives (cert paths, ciphers, HSTS)

### Phase 2: Routing
6. Proxy rules for `/synthesize`, `/jobs/*`, `/health`, `/admin/*` → upstream
7. Static alias for `/audio/` → `/data/audio/` with `try_files $uri =404`
8. Disable directory listing in `/data/audio/`
9. Add response headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`

### Phase 3: TLS + Renewal
10. Document: install Certbot (apt), obtain cert: `certbot certonly --webroot -w /var/www/letsencrypt -d tts.service`
11. Nginx config: reference cert paths (`ssl_certificate` / `ssl_certificate_key`)
12. Test renewal: `certbot renew --dry-run`
13. Add renewal cron: `0 12 * * * certbot renew --quiet` (daily check, renews 30 days before expiry)

### Phase 4: Testing & Docs
14. Copy config to live: `sudo cp nginx/tts-service.conf /etc/nginx/sites-available/`
15. Enable site: `sudo ln -s /etc/nginx/sites-available/tts-service /etc/nginx/sites-enabled/`
16. Validate: `sudo nginx -t` (must exit 0)
17. Reload: `sudo systemctl reload nginx`
18. Test routes: curl + chrome browser (mixed content checks)
19. Document in README: domain name, cert location, renewal process, emergency manual renewal command

---

## Blocking

- Requires: **API running on localhost:8080** (G1-G2 must be implemented first)
- Requires: **domain name registered + DNS pointing to server IP**
- Requires: **/data/audio/ directory exists** (from task A3)
- Note: Can develop with `server_name localhost;` and test cert for local dev

---

## Notes

**Caddy Alternative** (mentioned in shortcode):
```
If preferring Caddy over Nginx:
- Caddy automatically handles HTTPS (Let's Encrypt integration built-in)
- Simpler config: reverse_proxy / localhost:8080
- file_server /audio/* on /data/audio/
- Swap steps 3-13 with equivalent Caddy directives in Caddyfile
- Same DoD applies (routes, caching, headers)
```

**Self-Signed Cert for Dev:**
```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes
```

**Testing without DNS:**
```bash
curl -k -H "Host: tts.service" https://localhost/health
```

---

## Related Tasks
- A3 (Storage setup)
- G2 (Docker + docker-compose.yml)
- G4 (.env template)

---

## Research & Reference

### Key Patterns

- **`alias` statt `root` für `/audio/`:** `location /audio/ { alias /data/audio/; }` — `alias` ersetzt den Location-Prefix im Pfad. `root` würde `/data/audio//audio/` erzeugen (doppelter Prefix). `alias` ist richtig für Sub-Directory-Mounts.
- **`try_files $uri =404`:** In der `/audio/` Location: `try_files $uri =404;` — wenn Datei nicht existiert, 404 zurückgeben statt Directory-Listing oder Pass-Through. Kombination mit `autoindex off` für Sicherheit.
- **Cache-Control für Audio-Files:** `add_header Cache-Control "public, immutable, max-age=604800";` — `immutable` signalisiert dem Browser: URL ist stabil, nicht re-validieren. Passt perfekt zum Hash-basierten Dateinamen-Schema (ARCHITECTURE.md §6): gleiche URL = gleicher Inhalt, immer.
- **HTTP → HTTPS Redirect:** Separater `server`-Block auf Port 80: `return 301 https://$host$request_uri;`. Kein rewrite, direkt `return`.
- **Certbot Webroot Method:** `certbot certonly --webroot -w /var/www/letsencrypt -d domain.tld`. Nginx muss `location /.well-known/acme-challenge/ { root /var/www/letsencrypt; }` im HTTP-Block haben. Kein nginx-Plugin nötig (nur certonly).
- **Caddy als Alternative:** `Caddyfile` ist 5 Zeilen statt 60: `tts.service { reverse_proxy /api* localhost:8080; file_server /audio/* { root /data/audio } }`. Caddy managed HTTPS automatisch. Bei Neuinstallation: Caddy bevorzugen.

### Open Questions / Decisions

- **Nginx oder Caddy?** Caddy ist einfacher für neue Deployments (auto-HTTPS, simpler Config). Nginx ist bewährt und auf dem bestehenden Hetzner-Server wahrscheinlich schon installiert. → Entscheidung: Nginx als Primär-Config, Caddy-Alternative dokumentiert. Implementierer entscheidet je nach Server-Zustand.
- **Gzip für Audio?** MP3 ist bereits komprimiert. `gzip` auf `/audio/` deaktivieren (CPU-Waste ohne Benefit). Gzip nur für JSON-API-Responses (`application/json`).
- **`proxy_pass` Upstream:** `proxy_pass http://localhost:8080;` reicht für Single-Instance. Wenn später Skalierung auf mehreren API-Instanzen: `upstream`-Block mit mehreren Servern.

### Reference Links

- [Nginx `alias` Directive]: https://nginx.org/en/docs/http/ngx_http_core_module.html#alias
- [Nginx `try_files`]: https://nginx.org/en/docs/http/ngx_http_core_module.html#try_files
- [Cache-Control `immutable`]: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control#immutable
- [Certbot Webroot]: https://certbot.eff.org/instructions?os=debianbuster&tab=standard
- [Caddy docs]: https://caddyserver.com/docs/
- [Storage URL format]: ARCHITECTURE.md §6 (Auslieferung)
