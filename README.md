# Cyberpunk 2077 -> PiShock Local Middleware

This repo provides a local safety-focused middleware service that accepts signed game events and maps them to PiShock actions.

## Quick review: hard-mode scaling status
Yes — the current implementation includes the discussed hard-mode enemy scaling behavior:
- Enemy-aware intensity scaling (`enemy_count`, `enemies_nearby`, `enemy_wave`)
- Extra pulses from threshold + tier + in-combat combo bonus
- Bonus pulse cooldown guard to prevent spam
- Dynamic cadence reduction with minimum tick clamp
- Duration stacking with capped max multiplier
- Optional logarithmic diminishing returns

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

## Install these files (project setup)
### 1) Clone / place the repository
```bash
git clone <your-repo-url> Pishock-cyberpunk-2077
cd Pishock-cyberpunk-2077
```

### 2) Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3) Install package + dependencies
```bash
pip install -e .[dev]
```

### 4) Generate/update local config (safe to run repeatedly)
```bash
python -m middleware.setup_wizard
```

### 5) Start the middleware
```bash
uvicorn middleware.app:app --reload
```

---

## How this connects to Cyberpunk 2077 (what you need to install)
You need **two sides**:
1. This local middleware (this repo)
2. A game-side event emitter mod/script in Cyberpunk 2077

### A) Install Cyber Engine Tweaks (CET)
To send events from the game process, the easiest approach is CET + Lua script.

Typical CET mod folder location:
- `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/`

Create your mod folder, for example:
- `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/`

Put your Lua script as:
- `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/init.lua`

> You wrote “luna” — likely you meant **Lua** (used by CET).

### B) Emit events from game to middleware
You can emit directly by HTTP from Lua (if you have an HTTP-capable mod helper), or use a file bridge:
- Game writes JSON lines into a file.
- `middleware.file_ingest` tails that file and forwards signed events to `/event`.

This repo already includes the file-ingest bridge:
```bash
python -m middleware.file_ingest --file <path-to-jsonl> --secret <hmac-secret>
```

---

## File locations to use
### Middleware side
- Config file created by wizard: `middleware/config.yaml`
- Example template: `middleware/config.example.yaml`

### Cyberpunk side (recommended starter layout)
- Lua mod script:
  - `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/init.lua`
- Optional JSONL emitter output file (example):
  - `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl`

Then point ingester at that file:
```bash
python -m middleware.file_ingest \
  --file "/path/to/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl" \
  --secret "change-me"
```

---

## Event format expected by middleware
Each event must be JSON with:
- `event_type`
- `ts_ms`
- `session_id`
- `armed`
- `context` (object)

Example line in `events.jsonl`:
```json
{"event_type":"player_hard_mode_tick","ts_ms":1730000000000,"session_id":"run-1","armed":true,"context":{"max_hp":400,"current_hp":220,"damage":300,"enemy_count":4,"in_combat":true}}
```

For hard mode, include in `context`:
- `max_hp`
- `current_hp`
- optional: `damage`
- optional enemy fields: `enemy_count`, `enemies_nearby`, `enemy_wave`, `in_combat`

---

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

## Sign events (direct HTTP mode)
If you send directly to `/event`, sign request body with:
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

Hard mode logic:
1. First hard-mode event starts tracking a damage window (`damage` or `max_hp - current_hp`) and returns `hard_mode_started` without sending a shock.
2. Every cooldown tick (default 500ms), intensity scales by recovered HP ratio:
   `intensity = round((healed_hp / max_hp) * hard_mode_max_intensity)`
3. Tracking ends when `current_hp >= max_hp` (`hard_mode_completed`).

## Enemy-driven hard-mode scaling
Hard mode reads `enemy_count`, `enemies_nearby`, or `enemy_wave` and applies:
- Intensity multiplier scaling
- Bonus pulses by threshold/tier with global anti-spam cooldown
- Faster cadence in crowded fights with a minimum tick clamp
- Duration stacking per enemy with caps
- In-combat combo pulses
- Optional logarithmic diminishing returns

## Run tests
```bash
python -m pytest -q
```
