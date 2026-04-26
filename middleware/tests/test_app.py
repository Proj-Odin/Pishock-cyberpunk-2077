import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import middleware.app as app_module
from middleware.config import EventMapping, load_config
from middleware.pishock import BeepOnlyPiShockClient, DryRunPiShockClient, PiShockClient
from middleware.policy import PolicyEngine
from middleware.runtime_mode import RuntimeMode
from middleware.security import compute_signature


@pytest.fixture(autouse=True)
def _reset_app_state(monkeypatch) -> None:
    test_config = load_config(Path(app_module.__file__).with_name("config.example.yaml"))
    monkeypatch.setattr(app_module, "_config", test_config)
    monkeypatch.setattr(app_module, "_policy", PolicyEngine(test_config))
    monkeypatch.setattr(app_module, "_client", DryRunPiShockClient())
    monkeypatch.setattr(app_module, "_dry_run_client", DryRunPiShockClient())
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.TEST)
    app_module._sessions_armed.clear()
    app_module._emergency_stop = False
    app_module._policy._cooldowns.clear()
    app_module._policy._bonus_cooldowns.clear()
    app_module._policy._hard_mode_states.clear()


def _signed_body(payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    return body, compute_signature(app_module._config.hmac_secret, body)


def test_health() -> None:
    client = TestClient(app_module.app)
    res = client.get('/health')
    assert res.status_code == 200
    data = res.json()
    assert data["runtime_mode"] == "test"
    assert data["dry_run_config"] is True
    assert data["dry_run_effective"] is True
    assert data["real_pishock_enabled"] is False
    assert data["pishock_client_mode"] == "dry_run"
    assert data["dry_run_active"] is True
    assert data["real_pishock_client_enabled"] is False


def test_health_does_not_expose_secrets(monkeypatch) -> None:
    monkeypatch.setattr(
        app_module._config,
        "pishock",
        {
            "dry_run": False,
            "username": "secret-user",
            "api_key": "secret-key",
            "share_code": "secret-share",
        },
    )
    monkeypatch.setattr(app_module._config, "hmac_secret", "secret-hmac")

    res = TestClient(app_module.app).get('/health')

    assert res.status_code == 200
    response_text = res.text
    for secret in ("secret-user", "secret-key", "secret-share", "secret-hmac"):
        assert secret not in response_text


def test_test_mode_health_effective_dry_run_when_config_false() -> None:
    app_module._config.pishock["dry_run"] = False

    res = TestClient(app_module.app).get('/health')

    assert res.status_code == 200
    data = res.json()
    assert data["runtime_mode"] == "test"
    assert data["dry_run_config"] is False
    assert data["dry_run_effective"] is True
    assert data["real_pishock_enabled"] is False
    assert data["pishock_client_mode"] == "dry_run"


def test_event_rejected_without_arm() -> None:
    client = TestClient(app_module.app)
    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 200
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == "session_not_armed"


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


def test_event_unsigned_request_is_rejected() -> None:
    client = TestClient(app_module.app)
    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    res = client.post('/event', content=body, headers={"content-type": "application/json"})
    assert res.status_code == 401
    assert res.json()["detail"] == "invalid_signature"


def test_event_rejected_when_payload_armed_false() -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": False,
        "context": {},
    }
    body, sig = _signed_body(payload)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 200
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == "session_not_armed"


def test_emergency_stop_blocks_event_processing() -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    stop_res = client.post("/stop")
    assert stop_res.status_code == 200

    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 423
    assert res.json()["detail"] == "emergency_stop_enabled"


def test_emergency_stop_blocks_all_runtime_modes(monkeypatch) -> None:
    client = TestClient(app_module.app)
    payload = {
        "event_type": "player_healed",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)

    for mode in (RuntimeMode.TEST, RuntimeMode.BEEP, RuntimeMode.LIVE):
        app_module._sessions_armed["abc"] = True
        app_module._emergency_stop = True
        monkeypatch.setattr(app_module, "_runtime_mode", mode)
        res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
        assert res.status_code == 423
        assert res.json()["detail"] == "emergency_stop_enabled"


def test_hard_mode_is_blocked_when_shock_is_disabled() -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    payload = {
        "event_type": "player_hard_mode_tick",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {"max_hp": 100, "current_hp": 50, "damage": 50},
    }
    body, sig = _signed_body(payload)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 200
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == "shock_disabled"


def test_live_mode_still_respects_allow_shock_false(monkeypatch) -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.LIVE)
    payload = {
        "event_type": "player_hard_mode_tick",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {"max_hp": 100, "current_hp": 50, "damage": 50},
    }
    body, sig = _signed_body(payload)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})

    assert res.status_code == 200
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == "shock_disabled"


def test_beep_event_uses_dry_run_client_without_credentials() -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    payload = {
        "event_type": "player_healed",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 200
    assert res.json()["accepted"] is True
    assert "dry_run" in res.json()["pishock_response"]


def test_test_mode_player_healed_uses_dry_run_instead_of_real_client(monkeypatch) -> None:
    class RecordingDryRun:
        def __init__(self):
            self.calls: list[tuple[int, int, int]] = []

        async def operate(self, op: int, intensity: int, duration_s: int):
            self.calls.append((op, intensity, duration_s))
            return 200, f"dry_run op={op}"

    class RealClientShouldNotRun:
        def __init__(self):
            self.calls: list[tuple[int, int, int]] = []

        async def operate(self, op: int, intensity: int, duration_s: int):
            self.calls.append((op, intensity, duration_s))
            raise RuntimeError("real client should not run")

    dry_run = RecordingDryRun()
    real_client = RealClientShouldNotRun()
    app_module._config.pishock["dry_run"] = False
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.TEST)
    monkeypatch.setattr(app_module, "_dry_run_client", dry_run)
    monkeypatch.setattr(app_module, "_client", real_client)

    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    payload = {
        "event_type": "player_healed",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})

    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is True
    assert data["reason"] == "ok"
    assert "pishock_operate_failed" not in res.text
    assert dry_run.calls == [(2, 1, 1)]
    assert real_client.calls == []


def test_beep_mode_blocks_vibrate_before_client_call(monkeypatch) -> None:
    calls: list[tuple[int, int, int]] = []

    async def record_operate(op: int, intensity: int, duration_s: int):
        calls.append((op, intensity, duration_s))
        return 200, "should not run"

    app_module._config.pishock["dry_run"] = False
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.BEEP)
    monkeypatch.setattr(app_module._client, "operate", record_operate)

    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})

    assert res.status_code == 200
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == "runtime_mode_blocked"
    assert res.json()["error_code"] == "runtime_mode_blocked"
    assert calls == []


def test_beep_mode_blocks_shock_before_client_call(monkeypatch) -> None:
    calls: list[tuple[int, int, int]] = []

    async def record_operate(op: int, intensity: int, duration_s: int):
        calls.append((op, intensity, duration_s))
        return 200, "should not run"

    app_module._config.pishock["dry_run"] = False
    app_module._config.allow_shock = True
    app_module._config.event_mappings["shock_test"] = EventMapping(
        mode="shock",
        intensity=10,
        duration_ms=500,
        cooldown_ms=0,
    )
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.BEEP)
    monkeypatch.setattr(app_module._client, "operate", record_operate)

    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    payload = {
        "event_type": "shock_test",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})

    assert res.status_code == 200
    assert res.json()["accepted"] is False
    assert res.json()["reason"] == "runtime_mode_blocked"
    assert res.json()["error_code"] == "runtime_mode_blocked"
    assert calls == []


def test_event_returns_structured_error_when_pishock_fails(monkeypatch) -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    app_module._config.pishock["dry_run"] = False
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.LIVE)

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
    body, sig = _signed_body(payload)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is False
    assert data["reason"] == "pishock_operate_failed"
    assert data["error_code"] == "pishock_operate_failed"
    assert "error" not in data


def test_beep_mode_missing_python_pishock_returns_safe_error_code(monkeypatch) -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.BEEP)
    monkeypatch.setattr(app_module._config, "pishock", {
        "dry_run": False,
        "username": "user-secret",
        "api_key": "api-secret",
        "share_code": "share-secret",
        "name": "n",
    })
    monkeypatch.setattr(
        app_module,
        "_client",
        BeepOnlyPiShockClient(PiShockClient(app_module._config.pishock)),
    )

    payload = {
        "event_type": "player_healed",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})

    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is False
    assert data["reason"] == "pishock_operate_failed"
    assert data["error_code"] == "python_pishock_not_installed"
    response_text = res.text
    for secret in ("user-secret", "api-secret", "share-secret"):
        assert secret not in response_text


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
    app_module._config.pishock["dry_run"] = False
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.LIVE)

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
    start_body, start_sig = _signed_body(start_payload)
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
    tick_body, tick_sig = _signed_body(tick_payload)
    tick_res = client.post('/event', content=tick_body, headers={"x-signature": tick_sig, "content-type": "application/json"})

    assert tick_res.status_code == 200
    assert tick_res.json()["accepted"] is True
    assert calls
    assert calls[0][0] == 0


def test_success_response_redacts_pishock_client_text(monkeypatch) -> None:
    client = TestClient(app_module.app)
    app_module._sessions_armed["abc"] = True
    app_module._config.pishock["dry_run"] = False
    monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.LIVE)

    async def leaky_operate(op: int, intensity: int, duration_s: int):
        return 200, "api_key=raw-api-key share_code=raw-share username=raw-user"

    monkeypatch.setattr(app_module._client, "operate", leaky_operate)

    payload = {
        "event_type": "player_damaged",
        "ts_ms": 1,
        "session_id": "abc",
        "armed": True,
        "context": {},
    }
    body, sig = _signed_body(payload)

    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})

    assert res.status_code == 200
    assert res.json()["accepted"] is True
    assert "raw-api-key" not in res.text
    assert "raw-share" not in res.text
    assert "raw-user" not in res.text
    assert "[REDACTED]" in res.json()["pishock_response"]
