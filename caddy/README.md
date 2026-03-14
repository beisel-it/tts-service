# Caddy deployment

This folder contains a **Caddyfile template** for running `tts-service` behind Caddy.

## Validate

```bash
caddy validate --config caddy/Caddyfile
```

## Run (host install)

1) Install Caddy (recommended via official repository)
2) Copy the Caddyfile:

```bash
sudo cp caddy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

## Notes

- The template assumes the API is reachable at `localhost:8080`.
- Audio is served from `/data/audio` under `/audio/*` and gets `Cache-Control: public, max-age=604800`.
- API endpoints are forced to `Cache-Control: no-cache`.

Adjust `tts.service` to your real domain.
