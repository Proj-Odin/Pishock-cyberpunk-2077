# Middleware internals

## Endpoints
- `GET /health`
- `POST /arm/{session_id}`
- `POST /disarm/{session_id}`
- `POST /stop`
- `POST /resume`
- `POST /event`

## Event schema
```json
{
  "event_type": "player_damaged",
  "ts_ms": 1700000000000,
  "session_id": "run-1",
  "armed": true,
  "context": {}
}
```

## Signature header
`X-Signature: sha256=<hmac_hex>` where HMAC uses the request body bytes and `security.hmac_secret`.

## Safety model
- Session must be armed both by API (`/arm/{session_id}`) and payload (`armed=true`).
- Shock mapping is blocked unless `policy.allow_shock=true`.
- Cooldowns apply by `(session_id, event_type)`.
- Intensity and duration are hard-capped.
- Emergency stop blocks event handling.
