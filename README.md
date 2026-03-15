# Cyberpunk 2077 to PiShock Local Middleware

Local safety-focused middleware that accepts signed game events and maps them to PiShock actions.

## Features
- FastAPI service for receiving signed events.
- HMAC request verification (`X-Signature: sha256=<hex>`).
- Session arming/disarming and emergency stop.
- Policy allowlist with per-event cooldowns and clamp limits.
- Shock disabled by default unless explicitly enabled.
- Hard mode with healing-based scaling and enemy-aware modifiers.
- Optional JSONL ingest bridge for local event emitter workflows.
- PiShock setup wizard that is safe to rerun.

## Quick Start
```bash
bash scripts/setup_env.sh
python -m middleware.setup_wizard
uvicorn middleware.app:app --reload
```

## Windows Quick Start (PowerShell)
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1
python -m middleware.setup_wizard
uvicorn middleware.app:app --reload
```

If setup fails while creating `.venv`, run from an unrestricted shell with a writable `TEMP` directory.

## Setup Wizard
Run:
```bash
python -m middleware.setup_wizard
```

The wizard collects:
1. PiShock username
2. PiShock API key
3. PiShock share code
4. Sender name
5. Optional JSONL event file path (creates parent folders and file if needed)
6. Hard-mode enemy scaling options

## Ingest Bridge (JSONL -> /event)
```bash
python -m middleware.file_ingest \
  --file "C:/path/to/events.jsonl" \
  --secret "change-me"
```

Notes:
- Uses `http://127.0.0.1:8000/event` by default.
- Accepts JSONL files saved with or without a UTF-8 BOM.
- Keeps running on malformed lines and transient HTTP errors.

## Event Format
Each event sent to `/event` must include:
- `event_type`
- `ts_ms`
- `session_id`
- `armed`
- `context` (object)

Example:
```json
{"event_type":"player_hard_mode_tick","ts_ms":1730000000000,"session_id":"run-1","armed":true,"context":{"max_hp":400,"current_hp":220,"damage":300,"enemy_count":4,"in_combat":true}}
```

## Sign Events
If you POST directly to `/event`, sign the raw JSON body:
```python
import hmac, hashlib, json

secret = b"change-me"
payload = {
    "event_type": "player_damaged",
    "ts_ms": 1700000000000,
    "session_id": "run-1",
    "armed": True,
    "context": {"damage": 12},
}
body = json.dumps(payload, separators=(",", ":")).encode()
sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
print(f"sha256={sig}")
```

## Hard Mode
Configure an event mapping with `mode: hard` (example: `player_hard_mode_tick`).

Expected hard-mode context keys:
- `max_hp` (required)
- `current_hp` (required on tick events)
- `damage` (optional, used to seed initial damage window)
- Optional enemy fields: `enemy_count`, `enemies_nearby`, `enemy_wave`, `in_combat`

Behavior:
1. First hard-mode event starts a damage window and returns `hard_mode_started`.
2. Follow-up events scale intensity by recovered HP ratio.
3. When fully healed, returns `hard_mode_completed` and clears state.

Enemy scaling supports:
- Intensity multiplier
- Bonus pulses from thresholds and tiers
- Global anti-spam cooldown for bonus pulses
- Dynamic cadence reduction with minimum tick clamp
- Duration stacking with cap
- Optional in-combat combo pulse
- Optional logarithmic diminishing returns

## Run Tests
```bash
python -m pytest -q
```

## Package Repo Export
```bash
python scripts/package_repo.py
python scripts/package_repo.py --output ./exports/pishock-cyberpunk-2077.zip
```

Notes:
- Default output is `../pishock-cyberpunk-2077-export.zip`.
- `middleware/config.yaml` is excluded from exports.

## Important Files
- `middleware/config.example.yaml` (template)
- `middleware/config.yaml` (local runtime config, created by wizard)
- `middleware/app.py` (API server)
- `middleware/policy.py` (safety and hard-mode decisions)
- `middleware/pishock.py` (PiShock adapter)
- `middleware/file_ingest.py` (JSONL bridge)
