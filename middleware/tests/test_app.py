import json

import pytest
from fastapi.testclient import TestClient

import middleware.app as app_module
from middleware.security import compute_signature


@pytest.fixture(autouse=True)
def _reset_app_state() -> None:
    app_module._sessions_armed.clear()
    app_module._emergency_stop = False
    app_module._policy._cooldowns.clear()
    app_module._policy._bonus_cooldowns.clear()
    app_module._policy._hard_mode_states.clear()


def test_health() -> None:
    client = TestClient(app_module.app)
    res = client.get('/health')
    assert res.status_code == 200


def test_event_rejected_without_arm() -> None:
    client = TestClient(app_module.app)
    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = compute_signature(app_module._config.hmac_secret, body)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 200
    assert res.json()["accepted"] is False


def test_event_invalid_signature() -> None:
    client = TestClient(app_module.app)
    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    res = client.post('/event', content=body, headers={"x-signature": 'sha256=bad', "content-type": "application/json"})
    assert res.status_code == 401


def test_event_returns_structured_error_when_pishock_fails(monkeypatch) -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True

    async def fail_operate(op: int, intensity: int, duration_s: int):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module._client, "operate", fail_operate)

    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = compute_signature(app_module._config.hmac_secret, body)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is False
    assert data["reason"] == "pishock_operate_failed"


def test_event_invalid_payload_returns_400() -> None:
    client = TestClient(app_module.app)
    body = b"{not-json}"
    sig = compute_signature(app_module._config.hmac_secret, body)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 400
    assert res.json()["detail"] == "invalid_event_payload"


def test_hard_mode_uses_shock_operation_code(monkeypatch) -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    monkeypatch.setattr(app_module._config, "allow_shock", True)

    calls: list[tuple[int, int, int]] = []

    async def record_operate(op: int, intensity: int, duration_s: int):
        calls.append((op, intensity, duration_s))
        return 200, "ok"

    monkeypatch.setattr(app_module._client, "operate", record_operate)

    start_payload = {
        "event_type": "player_hard_mode_tick",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {"max_hp": 100, "current_hp": 50, "damage": 50},
    }
    start_body = json.dumps(start_payload, separators=(",", ":")).encode()
    start_sig = compute_signature(app_module._config.hmac_secret, start_body)
    start_res = client.post('/event', content=start_body, headers={"x-signature": start_sig, "content-type": "application/json"})
    assert start_res.status_code == 200
    assert start_res.json()["accepted"] is False
    assert start_res.json()["reason"] == "hard_mode_started"

    tick_payload = {
        "event_type": "player_hard_mode_tick",
        "ts_ms": 2,
        "session_id": "abc",
        "armed": True,
        "context": {"max_hp": 100, "current_hp": 60},
    }
    tick_body = json.dumps(tick_payload, separators=(",", ":")).encode()
    tick_sig = compute_signature(app_module._config.hmac_secret, tick_body)
    tick_res = client.post('/event', content=tick_body, headers={"x-signature": tick_sig, "content-type": "application/json"})

    assert tick_res.status_code == 200
    assert tick_res.json()["accepted"] is True
    assert calls
    assert calls[0][0] == 0
