# Cyberpunk 2077 -> PiShock Local Middleware

This repo provides a local safety-focused middleware service that accepts signed game events and maps them to PiShock actions.

## Features
- FastAPI service for receiving game events.
- HMAC request verification (`X-Signature: sha256=<hex>`).
- Session arming/disarming and emergency stop.
- Per-event cooldown and policy clamping.
- Shock disabled by default unless explicitly enabled.
- Optional JSONL file ingest utility for local event emitter workflows.
- Hard mode shock ramp based on recovered HP after a large hit.
- Streamlined PiShock integration via `python-pishock`.
- Guided setup wizard for PiShock credentials (safe to rerun).
- Enemy-driven hard-mode scaling options (intensity, extra pulses, cadence, duration tiers).

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python -m middleware.setup_wizard
uvicorn middleware.app:app --reload
```

## PiShock setup (python-pishock)
The setup wizard asks for:
1. Username
2. API key
3. Share code
4. Granular enemy-scaling controls (multiplier, diminishing returns, thresholds, tiers, cadence, duration, combo pulses, spacing)

It can be run multiple times and preserves existing config values when you press Enter.

Defaults are tuned for a stronger hard-mode feel (more extra pulses in larger fights).

Run:
```bash
python -m middleware.setup_wizard
```

## Sign events
```python
import hmac, hashlib, json
secret = b"change-me"
payload = {"event_type": "player_damaged", "ts_ms": 1700000000000, "session_id": "run-1", "armed": True, "context": {"damage": 12}}
body = json.dumps(payload, separators=(",", ":")).encode()
sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
print(f"sha256={sig}")
```

## Hard mode behavior
Configure an event mapping with `mode: hard` (example is `player_hard_mode_tick`).

Expected event payload context keys:
- `max_hp` (required)
- `current_hp` (required on tick events)
- `damage` (optional; used to seed initial damage window)

Hard mode logic:
1. First hard-mode event starts tracking a damage window (`damage` or `max_hp - current_hp`) and returns `hard_mode_started` without sending a shock.
2. Every cooldown tick (default 500ms), intensity scales by recovered HP ratio:
   `intensity = round((healed_hp / max_hp) * hard_mode_max_intensity)`
3. Tracking ends when `current_hp >= max_hp` (`hard_mode_completed`).

## Run tests
```bash
python -m pytest -q
```


## Enemy-driven hard-mode scaling
Hard mode now reads enemy context fields (`enemy_count`, `enemies_nearby`, or `enemy_wave`) and applies:
- Intensity multiplier scaling
- Bonus pulses by threshold/tier with global anti-spam cooldown
- Faster cadence in crowded fights with a minimum tick clamp
- Duration stacking per enemy with caps
- In-combat combo pulses
- Optional logarithmic diminishing returns
