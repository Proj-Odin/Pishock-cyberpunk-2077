# Middleware internals

## Endpoints
- `GET /health`
- `POST /arm/{session_id}`
- `POST /disarm/{session_id}`
- `POST /stop`
- `POST /resume`
- `POST /event`

`GET /health` includes `runtime_mode`, `dry_run_config`,
`dry_run_effective`, `real_pishock_enabled`, and `pishock_client_mode` so you
can confirm whether operations can reach a real PiShock client without exposing
credentials.

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
- Runtime mode `test` uses a mock PiShock client and sends no device/API operation.
- Runtime mode `beep` allows only beep operations through the real adapter.
- Runtime mode `live` requires explicit confirmation and still respects all policy controls.
- Config dry-run mode (`pishock.dry_run=true`) keeps the mock PiShock client enabled in every runtime mode.
- Shock mapping is blocked unless `policy.allow_shock=true`.
- Cooldowns apply by `(session_id, event_type)`.
- Intensity and duration are hard-capped.
- Emergency stop blocks event handling.

## PiShock integration flow
- Runtime uses `python-pishock` with:
  - `username`
  - `api_key`
  - `share_code`
- Runtime uses the dry-run client by default. Set `pishock.dry_run=false` only after configuring credentials and testing safely.
- Direct uvicorn startup reads `PISHOCK_RUNTIME_MODE` without prompting and defaults to `test`.
- Setup wizard collects these values and writes `middleware/config.yaml`.
- Setup wizard supports granular hard-mode enemy scaling controls and is safe to rerun.

## Troubleshooting operation failures
- If `pishock_operate_failed` happens in `test` mode, it is a bug: test mode
  should route mapped operations to dry-run and never call the real PiShock API.
- If `pishock_operate_failed` happens in `beep` or `live` mode, check PiShock
  credentials, share code, API availability, device status, and sanitized logs.
- If the operation error code is `python_pishock_not_installed`, beep/live mode
  needs the PiShock Python dependency before it can use the real adapter. Test
  mode does not require this dependency.
- Logs redact `api_key`, `username`, `share_code`, `hmac_secret`, `token`,
  `authorization`, and `x-signature`; do not add these values to issue reports.

## Hard mode
- Event mappings can set `mode: hard` to enable dynamic shock scaling from healing progression.
- First hard-mode event starts state and returns `hard_mode_started`.
- Follow-up events should include `context.max_hp` and `context.current_hp`.
- Output intensity is based on `healed_hp / max_hp` with the mapping intensity as the hard-mode max.
- Returns `hard_mode_completed` and clears state once `current_hp >= max_hp`.


## Enemy scaling in hard mode
Configured under `enemy_scaling` in config. Uses event context keys `enemy_count`, `enemies_nearby`, or `enemy_wave`.
Includes intensity multiplier, threshold/tier bonus pulses, cadence reduction, duration stacking, combat combo support, and diminishing returns.
