# Pronunciation CRUD API (Spec)

Goal: Provide an **auth-protected API** that allows consumers to manage pronunciation overrides ("pronunciation rules") without editing provider dictionaries manually.

Scope: **Per consumer token isolation** (each consumer can only read/write their own rules).

---

## Why

- ElevenLabs pronunciation dictionaries are powerful but require manual setup (dict ids, versions) and are not consumer-friendly.
- We want a product-grade feature: consumers can correct pronunciations (names, places) themselves.

---

## Non-goals (v1)

- No SSML `<phoneme>` authoring UI.
- No per-rule backend selection.
- No role-based permissions (all tokens are equal today).
- No automatic upload/sync to ElevenLabs pronunciation dictionaries.

---

## Data model

SQLite table: `pronunciations`

Columns:
- `id` (TEXT, primary key, e.g. `prn_<random>`)
- `owner_key_hash` (TEXT, **sha256** of consumer API key; never store raw key)
- `language` (TEXT, default `de-DE`)
- `grapheme` (TEXT) — the literal word to match, e.g. `Neckargerach`
- `alias` (TEXT) — replacement text, e.g. `Neckargehrach`
- `created_at` (TEXT ISO8601)
- `updated_at` (TEXT ISO8601)

Constraints:
- UNIQUE (`owner_key_hash`, `language`, `grapheme`)

Indexes:
- (`owner_key_hash`, `language`)

---

## API (admin)

All endpoints require `X-API-Key`.

### List
`GET /admin/pronunciations?language=de-DE`

Response:
```json
{
  "items": [
    {"id":"prn_...","language":"de-DE","grapheme":"Neckargerach","alias":"Neckargehrach","created_at":"...","updated_at":"..."}
  ]
}
```

### Create
`POST /admin/pronunciations`

Body:
```json
{"language":"de-DE","grapheme":"Neckargerach","alias":"Neckargehrach"}
```

### Update
`PUT /admin/pronunciations/{id}`

Body:
```json
{"alias":"Neckargehrach"}
```

### Delete
`DELETE /admin/pronunciations/{id}`

---

## Runtime behavior

### Preprocessing during synthesize

In the synthesize request path:
1) Determine `owner_key_hash` from the authenticated consumer token.
2) Load rules for (`owner_key_hash`, language).
3) Apply safe replacements:
   - whole-word boundaries (avoid replacing inside other words)
   - case-sensitive by default (option for case-insensitive later)
4) Send modified text to ElevenLabs.

### Language choice

- Default: `de-DE`
- Later: allow the synthesize payload to specify `language` (validated whitelist) or infer by voice.

---

## Tests (must)

- Auth required
- Isolation: token A cannot see token B rules
- Create/update/delete behave correctly
- Replacement logic is applied in synthesize path (unit test of preprocessor)

---

## Rollout plan (split PRs)

1) DB schema + CRUD endpoints (no synthesize integration yet)
2) Preprocessor + synthesize integration + tests
3) Docs update for consumers (how to use /admin/pronunciations)

---

## Security

- Store only `sha256(api_key)` as owner handle.
- Do not log raw keys.
- Validate max lengths for grapheme/alias.
