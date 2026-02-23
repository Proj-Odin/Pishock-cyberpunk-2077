# Project History

This document records **what changed**, **why it changed**, and **what outcomes/constraints were observed** across the repository’s development.

---

## Versioning and Release Mapping

The repository has been evolving commit-first. To improve release clarity, this history now maps milestones to proposed semantic versions.

| Proposed Version | Milestone | Primary Commits | Notes |
|---|---|---|---|
| `v0.0.0` | Repository initialized | `97c4f9e` | Baseline only |
| `v0.1.0` | Initial middleware scaffold | `ae7ad11` | First usable local bridge with safety policy |
| `v0.2.0` | Hard mode added | `6dcc677` | Healing-based dynamic shock ramp |
| `v0.2.1` | Documentation hardening | `73bfaa8` + current update | Historical and operational docs expanded |

### Suggested release-note strategy
- Derive release notes directly from this file sections:
  - **What we implemented**
  - **Outcome / edge cases**
  - **Operational notes**
- Keep a lightweight `CHANGELOG.md` later if releases become public-facing.

---

## 1) Initialization

**Commit:** `97c4f9e`

### What happened
- Created the repository baseline.

### Why
- Establish a clean starting point for a local Cyberpunk 2077 → PiShock middleware.

### Outcome
- Enabled incremental, reviewable implementation from an empty root.

---

## 2) Initial Middleware Scaffold (`v0.1.0`)

**PR title:** `Add local Cyberpunk→PiShock FastAPI middleware scaffold with safety policy and file-ingest`  
**Commit:** `ae7ad11`

### What we implemented
- FastAPI service endpoints:
  - `/health`
  - `/arm/{session_id}` / `/disarm/{session_id}`
  - `/stop` / `/resume`
  - `/event`
- Signed ingress using HMAC (`X-Signature: sha256=...`).
- PiShock HTTP client for approved operations.
- YAML-based configuration and example profile.
- Policy controls:
  - allowlisted event mappings,
  - arming requirement,
  - shock gating (`allow_shock`),
  - cooldowns,
  - intensity and duration clamping.
- Utilities and docs:
  - JSONL ingest CLI,
  - setup scripts,
  - README docs,
  - baseline unit tests.

### Why
- Create a local safety boundary between game events and hardware actions.
- Favor conservative defaults and explicit arming.
- Support local/offline workflows via signed payloads and file ingestion.

### Outcome / edge cases addressed
- Enforced denial paths for unmapped events, disarmed sessions, and invalid signatures.
- Established emergency stop path to block all event actuation.
- Environment dependency constraints identified early (install restrictions in CI/runtime shells).

---

## 3) Hard Mode (`v0.2.0`)

**PR title:** `Add hard mode with healing-based shock ramp progression`  
**Commit:** `6dcc677`

### What we implemented
- Added `mode: hard` to policy mappings.
- Added per-session hard-mode state machine.
- Hard-mode lifecycle:
  1. Start damage window (`hard_mode_started`).
  2. Tick during recovery and scale intensity by recovered HP ratio.
  3. End when fully recovered (`hard_mode_completed`).
- Formula:
  - `intensity = round((healed_hp / max_hp) * hard_mode_max_intensity)`
- API event path now passes event context into policy evaluation.
- Added hard-mode config example (`player_hard_mode_tick`, 500ms cooldown).
- Added tests for hard-mode ramp and completion.
- Made YAML import lazy inside config loader to reduce import-time failures when optional deps are unavailable.

### Why
- Match requested gameplay behavior where output ramps across healing progress rather than a static pulse.
- Keep deterministic and explainable scaling.

### Outcome / edge cases addressed
- Missing `max_hp` is rejected (`hard_mode_missing_max_hp`).
- No active damage window yields start/no-op semantics (`hard_mode_not_started`, `hard_mode_started`).
- No healing yet returns non-actuating state (`hard_mode_waiting_for_heal`).
- Completion clears session hard-mode state (`hard_mode_completed`).
- Shock-gating still applies (`allow_shock=false` blocks hard mode).

---

## Hard-Mode Visual Aid (Example Ramp)

Scenario: `max_hp=400`, initial damage window `300`, heal rate `100 HP/s`, sampled every `0.5s`, max hard intensity `20`.

| Time Window | Current HP | Healed HP | Ratio (`healed/max`) | Intensity (`round(ratio*20)`) | State |
|---|---:|---:|---:|---:|---|
| Start | 100 | 0 | 0/400 | 0 (no actuation) | `hard_mode_started` |
| 1s–2s | 200 | 100 | 0.25 | 5 | active |
| 2s–3s | 300 | 200 | 0.50 | 10 | active |
| 3s–4s | 400 | 300 | 0.75 | 15 | final active interval |
| 4s+ | 400 | complete | n/a | 0 | `hard_mode_completed` |

> Note: Exact per-tick calls depend on event emission cadence from the game side. Policy cooldown controls acceptance rate.

---

## Metrics and Benchmarking Notes

No formal latency/throughput benchmark suite is committed yet. Current operational posture:
- Hard mode uses a configurable cooldown (example: 500ms) to naturally limit output frequency.
- Policy cooldown and arming checks prevent unrestricted event floods from directly hitting PiShock API calls.

### Recommended benchmark plan (next)
- Measure end-to-end local latency (`event received` → `PiShock HTTP response`) at:
  - 2 events/sec,
  - 10 events/sec,
  - burst mode (50 events in 1s).
- Capture reject/accept ratios under cooldown.
- Track PiShock API error rate and timeout behavior under burst conditions.

---

## Dependencies and Compatibility

### Runtime stack
- Python `>=3.10`
- FastAPI
- Uvicorn
- HTTPX
- PyYAML

### Compatibility notes
- Config loading requires YAML at runtime.
- Lazy YAML import improves partial testability when PyYAML is missing.
- PiShock integration currently targets legacy HTTP operation endpoint semantics used in this project.

---

## Testing Notes and Coverage Snapshot

- Policy and security tests validate key decision logic paths.
- Full app tests require FastAPI to be installed in the execution environment.
- Current testing in restricted environments may be partial due to dependency/network limits.

> Coverage percentage is not currently published; a future CI step should generate and store `pytest --cov` output.

---

## Current Architecture Summary

- **Ingress:** HMAC-signed JSON event to `/event`.
- **Safety controls:** signature verification, session arming, emergency stop, policy allowlist, cooldowns, clamping.
- **Policy modes:** static (`shock`, `vibrate`, `beep`) and dynamic (`hard`).
- **Actuation:** PiShock HTTP request for accepted events.
- **Developer tooling:** setup scripts, file-ingest CLI, docs, unit tests.

---

## Next Steps / Open Issues

1. Add CI benchmarks for high-frequency event streams and cooldown efficacy.
2. Add integration tests that include app route behavior for hard mode with realistic tick payloads.
3. Add explicit release artifacts (`CHANGELOG.md`, version tags, GitHub releases).
4. Improve multi-session observability (per-session counters and active hard-mode state introspection endpoint).
5. Consider a small local UI for config editing and safety toggles.
6. Track PiShock API evolution and add adapter strategy for future endpoint changes.
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
