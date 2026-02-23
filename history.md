# Project History

This document summarizes the implementation history for the local **Cyberpunk 2077 -> PiShock middleware** in this repository, including what changed, why it changed, and how behavior evolved.

## Timeline

## 2025-02-23 — `97c4f9e` — Initialize repository

### What changed
- Repository bootstrapped with initial git metadata and baseline structure.

### Why
- Establish a clean starting point for middleware implementation.

### Outcome
- Ready for first implementation pass.

---

## 2025-02-23 — `ae7ad11` — Add local Cyberpunk→PiShock FastAPI middleware scaffold with safety policy and file-ingest

### What changed
- Added a FastAPI middleware service with core endpoints:
  - `GET /health`
  - `POST /arm/{session_id}`
  - `POST /disarm/{session_id}`
  - `POST /stop`
  - `POST /resume`
  - `POST /event`
- Added HMAC signature verification (`X-Signature`) to protect event integrity.
- Added config loading and an example config file for policy + PiShock credentials + event mappings.
- Added a policy engine with:
  - arming checks
  - cooldown checks
  - shock allow/deny gate (`allow_shock`)
  - hard caps for intensity and duration
- Added PiShock HTTP client integration for `apioperate` calls.
- Added JSONL file-ingest CLI for local/offline emitter workflows.
- Added setup helpers for Linux/macOS (`scripts/setup_env.sh`) and PowerShell (`scripts/setup_env.ps1`).
- Added tests for signature logic, policy behavior, and baseline API behavior.
- Added documentation (`README.md`, `middleware/README.md`) and packaging metadata (`pyproject.toml`).

### Why
- Create a safety-first local boundary between game events and physical device actions.
- Make development and validation practical with simple local tooling.
- Start with conservative defaults where shock remains disabled until explicitly enabled.

### Outcome
- A working scaffold for receiving signed game events and turning approved events into PiShock operations.

---

## 2025-02-23 — `6dcc677` — Add `hard` policy mode with healing-based shock ramp progression

### What changed
- Added a new `mode: hard` pathway in `PolicyEngine` for session-based dynamic shock scaling.
- Added `HardModeState` tracking per session:
  - `max_hp`
  - initial missing HP (damage window seed)
- Extended policy evaluation to accept event `context`, enabling HP-driven decisions.
- Implemented hard-mode lifecycle outcomes:
  - `hard_mode_started`
  - `hard_mode_waiting_for_heal`
  - `hard_mode_completed`
- Implemented healing-driven scaling formula:
  - `intensity = round((healed_hp / max_hp) * hard_mode_max_intensity)`
- Wired `/event` endpoint to pass payload context into policy evaluation.
- Added `player_hard_mode_tick` example mapping in config with 500ms cadence.
- Expanded docs to explain hard mode and the 400 HP / 300 damage progression example.
- Added/updated policy tests to validate hard-mode ramp and completion behavior.
- Changed YAML import to lazy-load inside `load_config()` so non-config tests can run in constrained environments.

### Why
- Address requirement for a deterministic “hard mode” that reacts over time while the player heals.
- Match expected progression behavior instead of firing one static action.
- Preserve existing safety controls and operational boundaries while adding dynamic behavior.

### Outcome
- Middleware now supports both standard fixed mappings and dynamic hard-mode mappings for progressive shock intensity during recovery.

---

## Current architecture summary

- **Ingress:** signed event POSTs from game-side emitters (or local tools).
- **Safety boundary:** middleware validates signature, session arm state, emergency stop, policy constraints.
- **Decision engine:** fixed-mode or hard-mode calculation with cooldown enforcement.
- **Actuation:** PiShock HTTP `apioperate` call with bounded intensity/duration.
- **Tooling:** docs, config template, setup scripts, tests, and JSONL ingest utility.

## Notes on test history

- In restricted environments, full test runs may fail if dependencies (e.g., FastAPI) cannot be installed.
- Policy/security-focused tests were still runnable and used to validate hard-mode behavior evolution.
