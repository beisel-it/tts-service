# Task: Webhook-Dispatcher
Shortcode: TTS-C3
Stage: todo
Status: ready for research
Priority: P2

## Definition of Done

- **Webhook Dispatch**: After Job transitions to `done` or `failed`, POST to `webhook_url` if set (from job record)
- **Payload Structure**: Request body contains exactly:
  - `job_id`: string
  - `article_id`: string | null
  - `status`: "done" | "failed"
  - `audio_url`: string
  - `duration_seconds`: number | null
  - `error`: string | null (only if status == "failed")
- **HMAC-SHA256 Signature**: Header `X-TTS-Signature` contains `sha256_hex(body + webhook_signing_secret)`
- **Consumer Validation**: Signature can be validated by consumer using shared secret from config
- **Retry Logic**: 
  - Max 3 attempts total
  - Exponential backoff: 2s, 5s, 10s
  - Only retry on network errors or 5xx; respect 4xx as permanent
- **Webhook Sent Tracking**: Update job.webhook_sent_at to ISO timestamp when successful
- **Error Handling**: Log failures without blocking job completion; job status remains `done` regardless
- **Testability**:
  - Unit tests for signature generation/validation
  - Integration tests with mock webhook endpoint
  - Tests for retry behavior (simulate timeouts, 5xx errors)

## Implementation Steps

1. **Create `app/worker/webhook.py`** with `WebhookDispatcher` class:
   - `async def dispatch(job: Job, webhook_url: str, signing_secret: str) -> bool`
   - Handle auth + timeout (config: `webhook.timeout_seconds`, default 10)
   - Implement retry loop (exponential backoff)
   - Return success bool

2. **Update `app/models.py`**:
   - Add `webhook_sent_at` field to Job model (nullable TEXT/datetime)

3. **Integrate into Worker**:
   - In `app/worker/worker.py`, after job transitions to `done`, call dispatcher
   - Wrap dispatch in try-except; log but do not raise

4. **Config Updates**:
   - `webhook.signing_secret` (env var: `WEBHOOK_SIGNING_SECRET`)
   - `webhook.timeout_seconds` (default 10)
   - `webhook.retry_attempts` (default 3)

5. **Tests** (`tests/test_webhook.py`):
   - Signature generation correctness
   - Retry logic with mock endpoints
   - Error handling (timeout, network, 5xx)

## Blocking / Dependencies

- **Depends on**: TTS-C2 (Worker-Loop) — needs job completion hook
- **Blocks**: None (non-critical feature; consumer can also poll)
- **External**: Requires `webhook.signing_secret` in config

## Notes

- Webhook is **fire-and-forget from worker perspective**: job is already done, webhook failure doesn't cause retry
- Consumer is responsible for idempotency (webhook can be called multiple times if worker retries)
- Signature uses HMAC-SHA256(body + secret) — standard practice for webhook security
