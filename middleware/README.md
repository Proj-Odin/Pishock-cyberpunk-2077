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

## PiShock integration flow
- Runtime uses `python-pishock` with:
  - `username`
  - `api_key`
  - `share_code`
- Setup wizard collects these values and writes `middleware/config.yaml`.

## Hard mode
- Event mappings can set `mode: hard` to enable dynamic shock scaling from healing progression.
- First hard-mode event starts state and returns `hard_mode_started`.
- Follow-up events should include `context.max_hp` and `context.current_hp`.
- Output intensity is based on `healed_hp / max_hp` with the mapping intensity as the hard-mode max.
- Returns `hard_mode_completed` and clears state once `current_hp >= max_hp`.


## Enemy scaling in hard mode
Configured under `enemy_scaling` in config. Uses event context keys `enemy_count`, `enemies_nearby`, or `enemy_wave`.
Includes intensity multiplier, threshold/tier bonus pulses, cadence reduction, duration stacking, combat combo support, and diminishing returns.
