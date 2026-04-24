from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from json import JSONDecodeError
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import ValidationError

from middleware.config import load_config
from middleware.logging_config import configure_logging, redact_text
from middleware.models import GameEvent
from middleware.pishock import OP_NAMES, RuntimeModeOperationBlocked, build_pishock_client
from middleware.policy import PolicyEngine
from middleware.runtime_mode import choose_runtime_mode
from middleware.security import verify_signature

_log_path = configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _log_startup_info()
    yield


app = FastAPI(title="Cyberpunk -> PiShock Middleware", lifespan=lifespan)

_runtime_config = Path(__file__).with_name("config.yaml")
_example_config = Path(__file__).with_name("config.example.yaml")
_config_source = _runtime_config if _runtime_config.exists() else _example_config
if not _runtime_config.exists():
    logger.warning("config.yaml missing; using example config source=%s", _example_config)
_config = load_config(_config_source)
_runtime_mode = choose_runtime_mode(interactive=False)
_policy = PolicyEngine(_config)


class _UnavailablePiShockClient:
    def __init__(self, error: Exception):
        self._error_type = type(error).__name__

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        raise RuntimeError(f"pishock_client_unavailable:{self._error_type}")


try:
    _client = build_pishock_client(_config.pishock, _runtime_mode)
except Exception as exc:
    logger.error("pishock client unavailable error_type=%s", type(exc).__name__)
    _client = _UnavailablePiShockClient(exc)

_sessions_armed: dict[str, bool] = {}
_emergency_stop = False


def _dry_run_enabled() -> bool:
    return bool(_config.pishock.get("dry_run", True))


def _log_startup_info() -> None:
    logger.info(
        "app started runtime_mode=%s config_source=%s dry_run=%s log_file=%s",
        _runtime_mode.value,
        _config_source,
        _dry_run_enabled(),
        _log_path,
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "runtime_mode": _runtime_mode.value,
        "armed_sessions": sum(1 for v in _sessions_armed.values() if v),
        "emergency_stop": _emergency_stop,
    }


@app.post("/arm/{session_id}")
def arm(session_id: str) -> dict:
    _sessions_armed[session_id] = True
    logger.info("session armed session_id=%s", session_id)
    return {"session_id": session_id, "armed": True}


@app.post("/disarm/{session_id}")
def disarm(session_id: str) -> dict:
    _sessions_armed[session_id] = False
    logger.info("session disarmed session_id=%s", session_id)
    return {"session_id": session_id, "armed": False}


@app.post("/stop")
def stop() -> dict:
    global _emergency_stop
    _emergency_stop = True
    logger.warning("emergency stop enabled")
    return {"emergency_stop": True}


@app.post("/resume")
def resume() -> dict:
    global _emergency_stop
    _emergency_stop = False
    logger.info("emergency stop resumed")
    return {"emergency_stop": False}


@app.post("/event")
async def event(request: Request, x_signature: str = Header(default="")) -> dict:
    body = await request.body()
    logger.info("event request received body_bytes=%s", len(body))
    if not verify_signature(_config.hmac_secret, body, x_signature):
        logger.warning("event rejected reason=invalid_signature")
        raise HTTPException(status_code=401, detail="invalid_signature")

    try:
        parsed = GameEvent.model_validate(json.loads(body))
    except (JSONDecodeError, ValidationError):
        logger.warning("event rejected reason=invalid_event_payload")
        raise HTTPException(status_code=400, detail="invalid_event_payload") from None

    if _emergency_stop:
        logger.warning(
            "event rejected event_type=%s session_id=%s reason=emergency_stop_enabled",
            parsed.event_type,
            parsed.session_id,
        )
        raise HTTPException(status_code=423, detail="emergency_stop_enabled")

    runtime_armed = _sessions_armed.get(parsed.session_id, False)
    armed = parsed.armed and runtime_armed
    logger.info(
        "event parsed event_type=%s session_id=%s payload_armed=%s runtime_armed=%s final_armed=%s",
        parsed.event_type,
        parsed.session_id,
        parsed.armed,
        runtime_armed,
        armed,
    )
    try:
        decision = _policy.evaluate(parsed.session_id, parsed.event_type, armed, parsed.context)
    except Exception as exc:
        logger.error(
            "policy evaluation failed event_type=%s session_id=%s error_type=%s error_detail=%s",
            parsed.event_type,
            parsed.session_id,
            type(exc).__name__,
            redact_text(str(exc)),
        )
        return {
            "accepted": False,
            "reason": "policy_evaluation_failed",
            "error_code": "policy_evaluation_failed",
        }
    if not decision.allowed:
        logger.warning(
            "event blocked event_type=%s session_id=%s reason=%s payload_armed=%s runtime_armed=%s final_armed=%s",
            parsed.event_type,
            parsed.session_id,
            decision.reason,
            parsed.armed,
            runtime_armed,
            armed,
        )
        return {"accepted": False, "reason": decision.reason}

    op = decision.op if decision.op is not None else 2
    intensity = decision.intensity if decision.intensity is not None else 1
    duration_s = decision.duration_s if decision.duration_s is not None else 1
    logger.info(
        "policy allowed event_type=%s session_id=%s op=%s intensity=%s duration_s=%s bonus_pulses=%s",
        parsed.event_type,
        parsed.session_id,
        OP_NAMES.get(op, f"unknown:{op}"),
        intensity,
        duration_s,
        decision.bonus_pulses,
    )

    try:
        status, text = await _client.operate(op, intensity, duration_s)

        bonus_results: list[dict] = []
        for _ in range(max(0, decision.bonus_pulses)):
            await asyncio.sleep(max(0, decision.pulse_spacing_ms) / 1000)
            bonus_intensity = max(
                1,
                min(_config.max_intensity, round(intensity * max(0.0, decision.bonus_intensity_ratio))),
            )
            b_status, b_text = await _client.operate(op, bonus_intensity, duration_s)
            bonus_results.append({"status": b_status, "response": b_text, "intensity": bonus_intensity})
    except RuntimeModeOperationBlocked as exc:
        logger.warning(
            "event rejected event_type=%s session_id=%s reason=runtime_mode_blocked block_reason=%s op=%s",
            parsed.event_type,
            parsed.session_id,
            str(exc),
            OP_NAMES.get(op, f"unknown:{op}"),
        )
        return {
            "accepted": False,
            "reason": "runtime_mode_blocked",
            "error_code": "runtime_mode_blocked",
        }
    except Exception as exc:
        logger.error(
            "pishock operation failed event_type=%s session_id=%s op=%s error_type=%s error_detail=%s",
            parsed.event_type,
            parsed.session_id,
            OP_NAMES.get(op, f"unknown:{op}"),
            type(exc).__name__,
            redact_text(str(exc)),
        )
        return {
            "accepted": False,
            "reason": "pishock_operate_failed",
            "error_code": "pishock_operate_failed",
        }

    logger.info(
        "event accepted event_type=%s session_id=%s op=%s intensity=%s duration_s=%s bonus_pulses_sent=%s status=%s",
        parsed.event_type,
        parsed.session_id,
        OP_NAMES.get(op, f"unknown:{op}"),
        intensity,
        duration_s,
        len(bonus_results),
        status,
    )
    return {
        "accepted": True,
        "reason": decision.reason,
        "pishock_status": status,
        "pishock_response": text,
        "bonus_pulses_sent": len(bonus_results),
        "bonus_results": bonus_results,
    }
