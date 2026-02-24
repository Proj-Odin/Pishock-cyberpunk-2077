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


## Windows 10 quick start (for first-time Python users)
If you've never used Python in terminal before, use **PowerShell**.

### 0) Confirm Python works
Open PowerShell and run:
```powershell
python --version
```
If that fails, install Python from python.org and re-open PowerShell.

### 1) Open project folder
```powershell
cd "C:\path\to\Pishock-cyberpunk-2077"
```

### 2) Create virtual environment
```powershell
python -m venv .venv
```

### 3) Activate virtual environment
```powershell
.\.venv\Scripts\Activate.ps1
```
If PowerShell blocks script execution (PSSecurityException), run one of these:

- **Recommended (current terminal only):**
```powershell
Set-ExecutionPolicy -Scope Process Bypass
```
- **Persistent for your user profile:**
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run activation again:
```powershell
.\.venv\Scripts\Activate.ps1
```

If you're using **Command Prompt (cmd.exe)** instead of PowerShell, use:
```cmd
.\.venv\Scripts\activate.bat
```

### 4) Install dependencies
```powershell
pip install -e .[dev]
```

### 5) Run setup wizard
```powershell
python -m middleware.setup_wizard
```
The wizard now:
- asks for PiShock fields,
- asks for enemy scaling options,
- validates/creates your JSON event file path.

### 6) Start middleware
```powershell
uvicorn middleware.app:app --reload
```
Leave this terminal open.

### 7) Start JSONL bridge (new terminal)
Open a second PowerShell window, activate venv again, then:
```powershell
python -m middleware.file_ingest --file "C:/Program Files (x86)/Steam/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl" --secret "change-me"
```

## Windows repair: `pydantic_core` import error
If you see this when starting middleware:

```text
ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'
```

Your virtualenv has a broken/incomplete compiled dependency install. Use this recovery flow in **PowerShell** from repo root.

### Fast repair in current `.venv`
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip uninstall -y pydantic pydantic-core fastapi uvicorn
.\.venv\Scripts\python.exe -m pip install --no-cache-dir fastapi uvicorn httpx pyyaml pishock pydantic pydantic-core
```
Then run middleware without reload first:
```powershell
.\.venv\Scripts\python.exe -m uvicorn middleware.app:app
```
If that works, optionally retry with reload:
```powershell
.\.venv\Scripts\python.exe -m uvicorn middleware.app:app --reload
```

### Clean rebuild (if fast repair fails)
```powershell
Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -Recurse -Force .\.venv
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install httpx fastapi uvicorn pyyaml pishock
```

Optional editable install after rebuild:
```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

Sanity check that compiled `pydantic_core` files exist:
```powershell
Get-ChildItem .\.venv\Lib\site-packages\pydantic_core
```

### Start commands after repair (2 terminals)
Terminal 1 (middleware):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\python.exe -m uvicorn middleware.app:app
```

Terminal 2 (ingester):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\python.exe -m middleware.file_ingest --file "G:/SteamLibrary/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl" --secret "change-me"
```

## Middleware 500 on `/event`: schema validation and 422 behavior
If ingester shows `500 Internal Server Error`, check middleware logs for missing required fields.
`GameEvent` requires:
- `event_type`
- `ts_ms`
- `session_id`

A line like below is **invalid** and will be rejected:
```json
{"event_type":"powershell_write_test"}
```

Use a valid test line instead:
```powershell
Add-Content "G:/SteamLibrary/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl" '{"event_type":"manual_test","ts_ms":1700000000001,"session_id":"ps-test","armed":false,"context":{"damage":1}}'
```

Clear old bad lines before retesting:
```powershell
Set-Content "G:/SteamLibrary/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl" ""
```

The middleware now returns **422** for invalid JSON or invalid event schema instead of surfacing a 500 traceback.

## One-block Windows recovery + run checklist
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
(Get-Content .\pyproject.toml) -replace 'python-pishock>=0\.1\.0','pishock>=1.0.0' | Set-Content .\pyproject.toml
Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force
if (Test-Path .\.venv) { Remove-Item -Recurse -Force .\.venv }
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e .[dev]
$eventsPath = "G:/SteamLibrary/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl"
New-Item -ItemType Directory -Path (Split-Path $eventsPath) -Force | Out-Null
if (-not (Test-Path $eventsPath)) { New-Item -ItemType File -Path $eventsPath -Force | Out-Null }
Write-Host "Run middleware:"; Write-Host ".\.venv\Scripts\python.exe -m uvicorn middleware.app:app"
Write-Host "Run ingester:"; Write-Host ".\.venv\Scripts\python.exe -m middleware.file_ingest --file `"$eventsPath`" --secret `"change-me`""
```

## How this connects to Cyberpunk 2077 (what you need to install)
You need **two sides**:
1. This local middleware (this repo)
2. A game-side event emitter mod/script in Cyberpunk 2077

### Cyberpunk checklist (explicit)
1. Install **Cyber Engine Tweaks (CET)**.
2. Create this folder:
   `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/`
3. Create this exact Lua file:
   `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/init.lua`

Use the regenerated template in this repo:
- Source template: `scripts/cet_init.lua`
- Copy it to your CET mod path above as `init.lua`.

Minimal inline Lua (same behavior as template):
```lua
local SESSION_ID = "cet-test"
local function now_ms() return math.floor(os.time() * 1000) end
local function emit_event_json(json_line) print("[PISHOCK_EVT] " .. json_line) end

registerForEvent("onInit", function()
  print("[pishock_bridge] loaded")
  emit_event_json('{"event_type":"player_damaged","ts_ms":' .. tostring(now_ms()) .. ',"session_id":"' .. SESSION_ID .. '","armed":true,"context":{"damage":1}}')
end)
```

4. Use setup wizard to validate/create the same JSON file path:
```bash
python -m middleware.setup_wizard
```
The wizard now creates parent folders and `events.jsonl` if missing.

5. Run file ingest bridge (separate terminal):
```bash
python -m middleware.file_ingest \
  --file "C:/Program Files (x86)/Steam/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl" \
  --secret "change-me"
```

> You wrote “luna” earlier — likely you meant **Lua** (used by CET).

---

## CET log transport fallback (when Lua `io.open` cannot write files)
If CET cannot append to `events.jsonl` even after permissions/path fixes, emit JSON through `print()` and ingest from `scripting.log`.

Lua example (inside `init.lua`):
```lua
local function emit_event_json(json_line)
  print("[PISHOCK_EVT] " .. json_line)
end

registerForEvent("onInit", function()
  print("[pishock_bridge] loaded")
  emit_event_json('{"event_type":"player_damaged","ts_ms":1700000000000,"session_id":"cet-test","armed":true,"context":{"damage":1}}')
end)
```

### Working order (3 terminals)
Terminal 1 — middleware:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\python.exe -m uvicorn middleware.app:app
```

Terminal 2 — arm matching session id (`cet-test`):
```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/arm/cet-test"
```

Terminal 3 — CET log ingester:
```powershell
.\.venv\Scripts\python.exe .\scripts\cet_log_ingest.py --log "G:/SteamLibrary/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/scripting.log" --secret "change-me" --timeout 10
```

If Terminal 3 shows `post failed: timed out`, middleware is unreachable/slow; verify Terminal 1 is running and retry with a higher `--timeout` value.

Sanity check CET log path first:
```powershell
Test-Path "G:/SteamLibrary/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/scripting.log"
```

The ingester script is self-contained and prepends repo root to `sys.path`, so no `PYTHONPATH` env variable is required.

If you get `{"accepted":false,"reason":"event_not_mapped"}`, the event `event_type` is valid JSON but missing from `event_mappings` in `middleware/config.yaml`. Run `python -m middleware.setup_wizard` or add a mapping manually.
If your CET log still shows `"event_type":"test_init"`, your game is still using an older `init.lua`; replace it with `scripts/cet_init.lua` and reload CET mods.

## File locations to use
### Middleware side
- Config file created by wizard: `middleware/config.yaml`
- Example template: `middleware/config.example.yaml`

### Cyberpunk side (recommended starter layout)
- Lua mod script:
  - `Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/init.lua`
- JSONL emitter output file (explicit path used above):
  - `C:/Program Files (x86)/Steam/steamapps/common/Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl`

## Windows troubleshooting for `events.jsonl` write failures (run in order)
If CET logs show it cannot write the events file, run these checks exactly in this order.

### 1) Confirm `events.jsonl` is a file (not a directory)
```powershell
$path = "G:\SteamLibrary\steamapps\common\Cyberpunk 2077\bin\x64\plugins\cyber_engine_tweaks\mods\pishock_bridge\events.jsonl"
Get-Item $path -Force | Format-List FullName,Attributes,Length,PSIsContainer,LastWriteTime
```
If `PSIsContainer : True`, it is a folder and must be removed/recreated as a file.

### 2) Clear read-only and grant write permission
```powershell
attrib -R "G:\SteamLibrary\steamapps\common\Cyberpunk 2077\bin\x64\plugins\cyber_engine_tweaks\mods\pishock_bridge\events.jsonl"
icacls "G:\SteamLibrary\steamapps\common\Cyberpunk 2077\bin\x64\plugins\cyber_engine_tweaks\mods\pishock_bridge" /grant "$env:USERNAME:(OI)(CI)(M)"
icacls "G:\SteamLibrary\steamapps\common\Cyberpunk 2077\bin\x64\plugins\cyber_engine_tweaks\mods\pishock_bridge\events.jsonl" /grant "$env:USERNAME:(M)"
```
Then validate writes from PowerShell:
```powershell
Add-Content $path '{"event_type":"powershell_write_test"}'
```

### 3) Print the real Lua error string
Use the exact `append_event` function from the Lua snippet above so CET logs include:
- `Permission denied`
- `No such file or directory`
- `Invalid argument`

### 4) Test with a relative CET path (recommended)
For Windows path/ACL sanity testing, switch to:
```lua
local events_path = "plugins/cyber_engine_tweaks/mods/pishock_bridge/events.jsonl"
```
This avoids absolute-drive permission quirks and keeps I/O inside CET's folder tree.

### 5) Test a definitely writable path
If it still fails, isolate whether SteamLibrary permissions are the problem:
```lua
local events_path = "C:/Temp/pishock_bridge/events.jsonl"
```
```powershell
New-Item -ItemType Directory -Path "C:\Temp\pishock_bridge" -Force | Out-Null
New-Item -ItemType File -Path "C:\Temp\pishock_bridge\events.jsonl" -Force | Out-Null
attrib -R "C:\Temp\pishock_bridge\events.jsonl"
```
If CET can write here but not under `G:\SteamLibrary\...`, your game folder path is blocked by permissions/security tooling.

### Where to read CET logs
- Mod-specific logs in your mod folder.
- Global `scripting.log` under the CET path tree.

Look for lines starting with:
- `[pishock_bridge] FAILED to open events file:`
- `[pishock_bridge] io.open error:`

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

## PiShock setup (pishock)
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

## Create a local zip export (optional)
This repo no longer stores a zip snapshot in-version-control.

If you need a local archive, generate one on demand:
```bash
python scripts/package_repo.py
```

The script writes `<repo-parent>/Pishock-cyberpunk-2077-export.zip` (for this workspace:
`/workspace/Pishock-cyberpunk-2077-export.zip`).
