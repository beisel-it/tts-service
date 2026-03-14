# Consumer Implementation Guide (tts.services.beisel.it)

This guide explains how to integrate with **tts-service** when it is deployed at:

- **Base URL:** `https://tts.services.beisel.it`

Assumption: you already have a valid **TTS API token**.

---

## 1) Authentication

All protected endpoints require a token in the `X-API-Key` header:

```http
X-API-Key: <YOUR_TTS_TOKEN>
```

Notes:
- This is **not** the ElevenLabs API key. Consumers never see provider credentials.
- `/health` is public.

---

## 2) Basic flow (recommended)

### Step A — Create a job

```bash
BASE_URL="https://tts.services.beisel.it"
TOKEN="<YOUR_TTS_TOKEN>"

curl -sS -X POST "$BASE_URL/synthesize" \
  -H "X-API-Key: $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary '{
    "text": "Hi.",
    "article_id": "example-article-001"
  }' | jq .
```

Response (example):

```json
{
  "job_id": "tts_1234abcd",
  "status": "pending",
  "audio_url": "https://tts.services.beisel.it/audio/<hash>.mp3",
  "poll_url": "https://tts.services.beisel.it/jobs/tts_1234abcd",
  "estimated_seconds": 2,
  "cached": false
}
```

### Step B — Poll until done/failed

```bash
JOB_ID="tts_1234abcd"

while true; do
  STATUS_JSON=$(curl -sS -H "X-API-Key: $TOKEN" "$BASE_URL/jobs/$JOB_ID")
  echo "$STATUS_JSON" | jq .

  STATUS=$(echo "$STATUS_JSON" | jq -r .status)
  [[ "$STATUS" == "done" || "$STATUS" == "failed" ]] && break
  sleep 1
done
```

### Step C — Download audio

When `status=done`, download the `audio_url`:

```bash
AUDIO_URL=$(echo "$STATUS_JSON" | jq -r .audio_url)

curl -L "$AUDIO_URL" -o /tmp/tts.mp3
file /tmp/tts.mp3
```

---

## 3) Idempotency and caching

### `article_id`

`article_id` is an optional consumer-provided idempotency key. If you send the same `(article_id + text)` again, the service may return a cached result.

Recommended practice:
- Use stable IDs: e.g. `news-2026-03-14-001`, `post-<slug>`, etc.

### Voice changes

If you need different voices for the same text, include the voice selection into your own idempotency key (e.g. `article_id = "<article>-voice-<id>"`).

---

## 4) Voice selection

You can pass an explicit voice id:

```json
{ "text": "...", "voice": "<elevenlabs_voice_id>" }
```

If you omit `voice`, the service uses its configured default.

Tip: ask the service what voices are available:

```bash
curl -sS -H "X-API-Key: $TOKEN" \
  "$BASE_URL/admin/voices?language=de" | jq .
```

---

## 5) Webhooks (optional)

If enabled server-side, you can provide `webhook_url` and receive a callback once done.

```json
{
  "text": "...",
  "article_id": "...",
  "webhook_url": "https://consumer.example.com/tts/webhook"
}
```

---

## 6) Error handling guidelines

- Treat `status=failed` as final.
- Common failure reasons:
  - provider quota / payment required
  - invalid voice id
  - transient network errors

Your consumer should:
- log `error` from `/jobs/{id}`
- optionally retry job creation (with a *new* `article_id`) if it was a transient outage

---

## 7) Minimal smoke test (copy/paste)

```bash
BASE_URL="https://tts.services.beisel.it"
TOKEN="<YOUR_TTS_TOKEN>"

JOB_JSON=$(curl -sS -X POST "$BASE_URL/synthesize" \
  -H "X-API-Key: $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary '{"text":"Hi.","article_id":"smoke-test-001"}')

echo "$JOB_JSON" | jq .
JOB_ID=$(echo "$JOB_JSON" | jq -r .job_id)

while true; do
  STATUS_JSON=$(curl -sS -H "X-API-Key: $TOKEN" "$BASE_URL/jobs/$JOB_ID")
  STATUS=$(echo "$STATUS_JSON" | jq -r .status)
  [[ "$STATUS" == "done" || "$STATUS" == "failed" ]] && break
  sleep 1
done

echo "$STATUS_JSON" | jq .

AUDIO_URL=$(echo "$STATUS_JSON" | jq -r .audio_url)
[[ "$AUDIO_URL" != "null" ]] && curl -L "$AUDIO_URL" -o /tmp/tts-smoke.mp3
ls -lh /tmp/tts-smoke.mp3
```
