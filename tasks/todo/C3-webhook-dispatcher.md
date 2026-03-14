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

---

## Research & Reference

### Key Patterns

- **HMAC-SHA256 Signatur:** `hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()` — Standard-Muster für Webhook-Signaturen (GitHub, Stripe nutzen dasselbe). `body_bytes = json.dumps(payload).encode('utf-8')`. Consumer validiert: gleiche Berechnung auf empfangener Body, dann `hmac.compare_digest(computed, received)`.
- **Payload als stabiles JSON:** `json.dumps(payload, sort_keys=True)` — `sort_keys=True` stellt sicher dass die Byte-Reihenfolge für die Signatur immer gleich ist, unabhängig von Dict-Insertion-Order. Wichtig: Consumer und Producer müssen dasselbe Serialisierungsformat nutzen.
- **Non-blocking Dispatch:** Webhook-Dispatch darf die Worker-Loop nicht blockieren. Da Worker bereits async ist: `asyncio.create_task(dispatcher.dispatch(...))` — fire-and-forget Task. Job-Status wird als `done` gesetzt bevor der Webhook-Call startet. Fehler im Webhook-Task werden gelogged, nicht propagiert.
- **`httpx.AsyncClient` mit Timeout:** `async with httpx.AsyncClient(timeout=10.0) as client: await client.post(webhook_url, ...)` — Timeout aus Config. Consumer-Endpoint kann langsam sein, Worker darf nicht hängen.
- **Retry-Backoff für Webhook:** 2s, 5s, 10s (wie im DoD). Nur bei Netzwerkfehlern und 5xx. Bei 4xx (Consumer-Seite falsch konfiguriert): sofort aufgeben, einmalig loggen. `tenacity` passt hier ebenfalls gut — `retry=retry_if_exception_type(httpx.HTTPStatusError) | retry_if_exception_type(httpx.NetworkError)`.
- **`webhook_sent_at` tracken:** Nach erfolgreichem Dispatch: `queue.update_webhook_sent(job_id, datetime.now(tz=UTC).isoformat())`. Falls alle Retries scheitern: Feld bleibt NULL — erkennbar für Monitoring.

### Open Questions / Decisions

- **`asyncio.create_task` vs direkt awaiten?** Create_task = fire-and-forget, Worker läuft weiter. Direct await = Worker wartet auf Webhook. → Create_task empfohlen: Webhook-Latenz gehört nicht zur Job-Processing-Zeit. Aber: Task muss irgendwo referenziert bleiben (sonst GC), z.B. in einem Set `_pending_tasks`.
- **Webhook-Fehler loggen auf welchem Level?** Alle Retries erschöpft: WARNING (kein ERROR, weil Job erfolgreich ist). Einzelner Retry-Fehler: DEBUG.
- **Content-Type des Webhook-Calls:** `application/json` — Consumer erwartet JSON. Charset: UTF-8 explizit setzen: `Content-Type: application/json; charset=utf-8`.
- **Idempotenz auf Consumer-Seite:** Consumer muss selbst idempotent sein (Webhook kann mehrfach kommen wenn Worker neu startet). Das ist ausdrücklich Consumer-Verantwortung laut Architecture-Doc.

### Reference Links

- [HMAC-SHA256 Python]: https://docs.python.org/3/library/hmac.html
- [GitHub Webhook Signature Pattern]: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- [asyncio.create_task]: https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
- [tenacity retry]: https://tenacity.readthedocs.io/ (auch in D3 Research)
- [Webhook spec]: ARCHITECTURE.md §3.3
- [Config (webhook section)]: ARCHITECTURE.md §7
- [C2 Worker Integration]: C2-worker-loop.md §6 (Webhook Dispatch)
