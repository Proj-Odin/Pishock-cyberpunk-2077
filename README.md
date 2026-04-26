# Cyberpunk 2077 to PiShock Local Middleware

Local FastAPI middleware that accepts HMAC-signed Cyberpunk 2077 events and maps them to PiShock actions with conservative safety gates.

Safe defaults:
- Runtime mode defaults to `test`.
- `policy.allow_shock` defaults to `false`.
- `pishock.dry_run` defaults to `true`.
- `middleware/config.yaml` is ignored by git.
- Tests never call the real PiShock API or hardware.

## Windows PowerShell Quick Start

Use two PowerShell windows:
- Window 1 runs the middleware server and stays open.
- Window 2 sends health checks and demo events.

Run the setup steps first. After setup, activate the environment every time you
open a new PowerShell window for this project.

### Step 1: Clone the repo

```powershell
git clone https://github.com/Proj-Odin/Pishock-cyberpunk-2077
cd Pishock-cyberpunk-2077
```

If you already cloned the repo, just go to the project folder:

```powershell
cd path\to\Pishock-cyberpunk-2077
```

### Step 2: Create the Python virtual environment

Do this once:

```powershell
py -m venv .venv
```

### Step 3: Activate the environment

Do this every time you open a new PowerShell window for this project:

```powershell
.\.venv\Scripts\Activate.ps1
```

After activation, your prompt usually starts with `(.venv)`.

### Step 4: Install dependencies

Do this after creating and activating the environment:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 5: Create your local config

Do this once:

```powershell
copy middleware\config.example.yaml middleware\config.yaml
```

If `middleware\config.yaml` already exists, keep it and edit it locally instead
of overwriting it.

For first use, leave the safe defaults:
- `pishock.dry_run: true`
- `policy.allow_shock: false`

### Step 6: Run tests

Run this before starting the middleware:

```powershell
python -m pytest -q
```

Expected result: all tests pass. Automated tests never call the real PiShock API
or hardware.

### Step 7: Start the middleware in safe test mode

Use PowerShell window 1. Keep this window open:

```powershell
cd path\to\Pishock-cyberpunk-2077
.\.venv\Scripts\Activate.ps1
$env:PISHOCK_RUNTIME_MODE="test"
python -m middleware.run
```

Test mode is the safe default. It uses dry-run/mock behavior and does not call
the real PiShock API or device.

### Step 8: Verify health from a second PowerShell window

Use PowerShell window 2:

```powershell
cd path\to\Pishock-cyberpunk-2077
.\.venv\Scripts\Activate.ps1
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected safe test-mode fields:

```text
runtime_mode: test
dry_run_effective: True
real_pishock_enabled: False
pishock_client_mode: dry_run
```

### Step 9: Send a safe demo event

Still in PowerShell window 2:

```powershell
python -m middleware.demo_event --event-type player_healed --context-json "{}"
```

Expected result:
- The session arms successfully.
- The event response has `accepted=true`.
- The PiShock response contains `dry_run`.
- No real PiShock API/device operation occurs.

## Windows Runtime Modes

### Safe Test Mode

Use this for setup, development, and verification:

```powershell
$env:PISHOCK_RUNTIME_MODE="test"
python -m middleware.run
```

### Beep-Only Manual Check

Use this only after test mode works. Beep mode can call the real PiShock API and
device if `pishock.dry_run: false` in `middleware\config.yaml`.

```powershell
$env:PISHOCK_RUNTIME_MODE="beep"
python -m middleware.run
```

Beep mode allows only PiShock beep operations to reach the real adapter. It
blocks vibrate and shock before any real client call. If `pishock.dry_run: true`,
beep mode still uses the mock client.

### Live Mode

Use live mode only after explicit confirmation and after checking your config.
Live mode can use real configured PiShock behavior.

```powershell
$env:PISHOCK_RUNTIME_MODE="live"
python -m middleware.run
```

Live mode prompts for this exact confirmation before real configured behavior is enabled:

```text
I UNDERSTAND LIVE MODE
```

### Direct Uvicorn Safe Mode

Most users should use `python -m middleware.run`. Direct uvicorn is mainly for
development:

```powershell
$env:PISHOCK_RUNTIME_MODE="test"
python -m uvicorn middleware.app:app --reload
```

Confirm the app is listening from another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The health response includes `runtime_mode`, `dry_run_config`,
`dry_run_effective`, `real_pishock_enabled`, and `pishock_client_mode`. In safe
test mode, `dry_run_effective` should be `True` and `real_pishock_enabled`
should be `False`, even if your local config has `pishock.dry_run: false`.

### Logs and Troubleshooting

By default, middleware logs are written to:

```text
.\logs\middleware.log
```

The log file is created automatically when the app starts. It uses rotation and is ignored by git.

Set debug logging in PowerShell:

```powershell
$env:PISHOCK_LOG_LEVEL="DEBUG"
python -m middleware.run
```

Tail logs in PowerShell:

```powershell
Get-Content .\logs\middleware.log -Wait
```

Useful things to look for:
- `runtime_mode=test`, `runtime_mode=beep`, or `runtime_mode=live`
- `event request received`
- `invalid_signature`
- `session_not_armed`
- `emergency_stop_enabled`
- `event blocked`
- `policy allowed`
- `dry-run operation`
- `runtime_mode_beep_blocks_non_beep_operation`
- `pishock operation failed`

If `pishock_operate_failed` happens in `test` mode, treat it as a bug: mapped
events should use dry-run and should not call the real PiShock API or device.
If it happens in `beep` or `live` mode, check credentials, share code, PiShock
API availability, device status, and the sanitized log entry.

### Beep mode error: `python_pishock_not_installed`

Test mode does not require `python-pishock`, PiShock credentials, API access, or
real hardware. Beep mode is different: it is a manual real API/device
connectivity check, limited to beep operations only. If beep mode returns
`error_code=python_pishock_not_installed`, install/check the PiShock Python
dependency and verify your local PiShock config before retrying beep mode.

Use test mode first:

```powershell
$env:PISHOCK_RUNTIME_MODE="test"
python -m middleware.run
```

In another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
python -m middleware.demo_event --event-type player_healed --context-json "{}"
```

Logs redact known sensitive fields such as `api_key`, `username`, `share_code`, `hmac_secret`, `secret`, `token`, `authorization`, and `x-signature`. Do not paste full logs publicly without checking them first.

Before sharing logs, make a copy and search it for private values from your local `middleware\config.yaml`. The redaction filter is a safety net, not a substitute for review. Share only the smallest relevant excerpt, and remove session IDs or local file paths if you consider them private.

### Windows Troubleshooting

Problem:

```text
event_status=200 event_response={"accepted":false,"reason":"pishock_operate_failed"}
```

First check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health | ConvertTo-Json -Depth 5
```

If `runtime_mode` is `beep`, you are in manual beep/API mode. Install/check
`python-pishock`, credentials, share code, API access, and hardware. For safe
dry-run, restart with:

```powershell
$env:PISHOCK_RUNTIME_MODE="test"
python -m middleware.run
```

If `runtime_mode` is `test`, this is a bug. Test mode should dry-run and never
call PiShock.

If PowerShell blocks venv activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

If `python` points to the wrong version:

```powershell
py -m venv .venv
where python
python --version
```

Use `python -m pip` instead of bare `pip`.

If `python -m uvicorn middleware.app:app --reload` fails in a restricted shell with `PermissionError: [WinError 5] Access is denied`, run it from a normal unrestricted PowerShell window. You can also run without reload:

```powershell
$env:PISHOCK_RUNTIME_MODE="test"
python -m uvicorn middleware.app:app
```

## Linux Setup

```bash
git clone https://github.com/Proj-Odin/Pishock-cyberpunk-2077
cd Pishock-cyberpunk-2077

python3 -m venv .venv
. .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cp -n middleware/config.example.yaml middleware/config.yaml

python -m pytest -q
```

Linux startup:

```bash
export PISHOCK_RUNTIME_MODE=test
python -m middleware.run
```

Direct uvicorn:

```bash
export PISHOCK_RUNTIME_MODE=test
python -m uvicorn middleware.app:app --reload
```

## Runtime Modes

Mode selection precedence:
1. CLI argument, such as `python -m middleware.run --mode beep`
2. `PISHOCK_RUNTIME_MODE`
3. Interactive prompt in `python -m middleware.run`
4. Safe fallback to `test`

Supported modes:
- `test`: dry-run/mock only. No PiShock API or device calls are made.
- `beep`: real PiShock adapter may be used for beep only. Vibrate and shock are blocked in the dispatch layer.
- `live`: real configured behavior may be used after explicit confirmation.

Invalid or missing mode values safely fall back to `test`.

Direct uvicorn startup never prompts. It reads `PISHOCK_RUNTIME_MODE`; if unset, invalid, or unconfirmed live mode, it uses `test`. To run direct uvicorn in live mode non-interactively, set both:

```powershell
$env:PISHOCK_RUNTIME_MODE="live"
$env:PISHOCK_LIVE_CONFIRMATION="I UNDERSTAND LIVE MODE"
python -m uvicorn middleware.app:app --reload
```

Real hardware/API use also requires `middleware\config.yaml` to contain credentials and `pishock.dry_run: false`. Shock and hard mode additionally require `policy.allow_shock: true`.

## Runtime Endpoints

- `GET /health`
- `POST /arm/{session_id}`
- `POST /disarm/{session_id}`
- `POST /stop`
- `POST /resume`
- `POST /event`

`/event` requires `X-Signature: sha256=<hex>` over the exact raw JSON body. Events do not operate unless HMAC is valid, the session is runtime-armed, payload `armed` is `true`, the event is mapped, policy allows it, and emergency stop is not enabled.

## Safe Config

`middleware/config.example.yaml` is non-secret and safe by default:

```yaml
policy:
  allow_shock: false
pishock:
  dry_run: true
  username: ""
  api_key: ""
  share_code: ""
```

Never commit `middleware/config.yaml`, real PiShock credentials, real HMAC secrets, `.env` files, logs, or local `events.jsonl`.

## Setup Wizard

```powershell
python -m middleware.setup_wizard
```

The wizard preserves existing values where possible. Dry-run mode can be used without PiShock credentials. If dry-run is disabled, username, API key, and share code are required.

## Run Tests

```powershell
python -m pytest -q
```

## Send a Demo Event

Start the middleware in one PowerShell window, then in another:

```powershell
python -m middleware.demo_event --event-type player_healed --context-json "{}"
```

The demo signs the event with the configured HMAC secret, checks `/health`,
prints the runtime mode, and arms `demo-run` unless `--skip-arm` is passed.
The base URL defaults to `http://127.0.0.1:8000`; override it with `--base-url`,
the backward-compatible `--url`, or `PISHOCK_BASE_URL`. Connection failures are
shown as friendly PowerShell instructions.

## JSONL Ingest

The ingest bridge tails a JSONL file and forwards each valid line to `/event` with a fresh HMAC signature:

```powershell
python -m middleware.file_ingest --file "events.jsonl" --secret "change-me"
```

Malformed JSONL lines are skipped with a clear stderr message. Transient HTTP errors are reported and the ingest loop continues.

## Generate a Test HMAC Signature

PowerShell:

```powershell
@'
import hashlib
import hmac
import json

secret = "change-me"
payload = {"event_type":"player_healed","ts_ms":1700000000000,"session_id":"demo-run","armed":True,"context":{}}
body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
print(body.decode("utf-8"))
print(f"X-Signature: sha256={signature}")
'@ | python
```

## Cyber Engine Tweaks Path

Expected Lua-side entrypoint:

```text
<Cyberpunk 2077>\bin\x64\plugins\cyber_engine_tweaks\mods\pishock_bridge\init.lua
```

Typical JSONL event file:

```text
<Cyberpunk 2077>\bin\x64\plugins\cyber_engine_tweaks\mods\pishock_bridge\events.jsonl
```

Point `python -m middleware.file_ingest --file` at that JSONL file.

## Hard Mode

Configure an event mapping with `mode: hard`, such as `player_hard_mode_tick`.

Expected context keys:
- `max_hp`
- `current_hp`
- Optional `damage`
- Optional enemy fields: `enemy_count`, `enemies_nearby`, or `enemy_wave`
- Optional `in_combat`

Flow:
1. First hard-mode event starts a damage window and returns `hard_mode_started`.
2. Follow-up events wait until HP recovery is detected.
3. Recovery pulses are clamped by policy intensity, duration, cooldown, cadence, and bonus pulse caps.
4. Full recovery returns `hard_mode_completed` and clears session state.

## Local Smoke Test

PowerShell window 1:

```powershell
$env:PISHOCK_RUNTIME_MODE="test"
python -m middleware.run
```

PowerShell window 2:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
python -m middleware.demo_event --event-type player_healed --context-json "{}"
```

Expected result: `/health` returns `status: ok`, `runtime_mode: test`,
`dry_run_effective: True`, and `real_pishock_enabled: False`; the demo response
includes `accepted: true` with a `dry_run` PiShock response.

## Beep Mode Smoke Test

PowerShell window 1:

```powershell
$env:PISHOCK_RUNTIME_MODE="beep"
python -m middleware.run
```

PowerShell window 2:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
python -m middleware.demo_event --event-type player_healed --context-json "{}"
```

Expected result with `pishock.dry_run: true`: dry-run success. Expected result
with `pishock.dry_run: false`: only beep may reach the real adapter; missing
dependency/config/API/device issues are reported safely, for example
`error_code=python_pishock_not_installed`.
