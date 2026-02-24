-- Cyber Engine Tweaks starter script for PiShock bridge.
-- Copy this file to:
--   Cyberpunk 2077/bin/x64/plugins/cyber_engine_tweaks/mods/pishock_bridge/init.lua

local SESSION_ID = "cet-test"

local function now_ms()
  return math.floor(os.time() * 1000)
end

local function emit_event_json(json_line)
  -- CET writes print() output to scripting.log.
  -- scripts/cet_log_ingest.py forwards lines prefixed with [PISHOCK_EVT].
  print("[PISHOCK_EVT] " .. json_line)
end

registerForEvent("onInit", function()
  print("[pishock_bridge] loaded")

  -- Default smoke-test event (mapped by default in middleware config).
  emit_event_json(
    '{"event_type":"player_damaged","ts_ms":' .. tostring(now_ms()) .. ',"session_id":"' .. SESSION_ID .. '","armed":true,"context":{"damage":1}}'
  )

  -- Optional hard-mode tick example (uncomment if you map/use player_hard_mode_tick):
  -- emit_event_json(
  --   '{"event_type":"player_hard_mode_tick","ts_ms":' .. tostring(now_ms()) .. ',"session_id":"' .. SESSION_ID .. '","armed":true,"context":{"max_hp":400,"current_hp":220,"damage":180,"enemy_count":3,"in_combat":true}}'
  -- )
end)
