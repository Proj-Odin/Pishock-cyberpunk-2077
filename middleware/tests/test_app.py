import json

from fastapi.testclient import TestClient

import middleware.app as app_module
from middleware.security import compute_signature


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


def test_event_invalid_payload_returns_422() -> None:
    client = TestClient(app_module.app)
    body = b'{"event_type":"powershell_write_test"}'
    sig = compute_signature(app_module._config.hmac_secret, body)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 422
    data = res.json()
    assert data["detail"]["error"] == "invalid_event"


def test_event_invalid_json_returns_422() -> None:
    client = TestClient(app_module.app)
    body = b'{"event_type":'
    sig = compute_signature(app_module._config.hmac_secret, body)
    res = client.post('/event', content=body, headers={"x-signature": sig, "content-type": "application/json"})
    assert res.status_code == 422
    assert "invalid_json" in res.json()["detail"]
