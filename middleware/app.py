from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request

from middleware.config import load_config
from middleware.models import GameEvent
from middleware.pishock import PiShockClient
from middleware.policy import PolicyEngine
from middleware.security import verify_signature

app = FastAPI(title="Cyberpunk -> PiShock Middleware")

_config = load_config(Path(__file__).with_name("config.yaml")) if Path(__file__).with_name("config.yaml").exists() else load_config(Path(__file__).with_name("config.example.yaml"))
_policy = PolicyEngine(_config)
_client = PiShockClient(_config.pishock)
_sessions_armed: dict[str, bool] = {}
_emergency_stop = False


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "armed_sessions": sum(1 for v in _sessions_armed.values() if v), "emergency_stop": _emergency_stop}


@app.post("/arm/{session_id}")
def arm(session_id: str) -> dict:
    _sessions_armed[session_id] = True
    return {"session_id": session_id, "armed": True}


@app.post("/disarm/{session_id}")
def disarm(session_id: str) -> dict:
    _sessions_armed[session_id] = False
    return {"session_id": session_id, "armed": False}


@app.post("/stop")
def stop() -> dict:
    global _emergency_stop
    _emergency_stop = True
    return {"emergency_stop": True}


@app.post("/resume")
def resume() -> dict:
    global _emergency_stop
    _emergency_stop = False
    return {"emergency_stop": False}


@app.post("/event")
async def event(request: Request, x_signature: str = Header(default="")) -> dict:
    if _emergency_stop:
        raise HTTPException(status_code=423, detail="emergency_stop_enabled")

    body = await request.body()
    if not verify_signature(_config.hmac_secret, body, x_signature):
        raise HTTPException(status_code=401, detail="invalid_signature")

    parsed = GameEvent.model_validate(json.loads(body))

    runtime_armed = _sessions_armed.get(parsed.session_id, False)
    armed = parsed.armed and runtime_armed
    decision = _policy.evaluate(parsed.session_id, parsed.event_type, armed, parsed.context)
    if not decision.allowed:
        return {"accepted": False, "reason": decision.reason}

    status, text = await _client.operate(decision.op or 2, decision.intensity or 1, decision.duration_s or 1)

    bonus_results: list[dict] = []
    for _ in range(max(0, decision.bonus_pulses)):
        await asyncio.sleep(max(0, decision.pulse_spacing_ms) / 1000)
        bonus_intensity = max(1, round((decision.intensity or 1) * max(0.0, decision.bonus_intensity_ratio)))
        b_status, b_text = await _client.operate(decision.op or 2, bonus_intensity, decision.duration_s or 1)
        bonus_results.append({"status": b_status, "response": b_text, "intensity": bonus_intensity})

    return {
        "accepted": True,
        "reason": decision.reason,
        "pishock_status": status,
        "pishock_response": text,
        "bonus_pulses_sent": len(bonus_results),
        "bonus_results": bonus_results,
    }
    return {"accepted": True, "reason": decision.reason, "pishock_status": status, "pishock_response": text}
