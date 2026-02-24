import asyncio
import sys
import types

from middleware.pishock import PiShockClient


class FakeShocker:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def shock(self, duration: int, intensity: int):
        return {"op": "shock", "duration": duration, "intensity": intensity}

    def vibrate(self, duration: int, intensity: int):
        return {"op": "vibrate", "duration": duration, "intensity": intensity}

    def beep(self, duration: int, intensity: int):
        return {"op": "beep", "duration": duration, "intensity": intensity}


def test_pishock_client_uses_python_library(monkeypatch):
    fake_module = types.SimpleNamespace(Shocker=FakeShocker)
    monkeypatch.setitem(sys.modules, "pishock", fake_module)

    client = PiShockClient({"username": "u", "api_key": "k", "share_code": "code", "name": "n"})

    status, text = asyncio.run(client.operate(op=1, intensity=10, duration_s=1))
    assert status == 200
    assert "vibrate" in text


def test_pishock_client_requires_credentials():
    try:
        PiShockClient({"username": "u", "api_key": "k", "share_code": ""})
        raise AssertionError("expected runtime error")
    except RuntimeError as exc:
        assert str(exc) == "pishock_credentials_missing"


def test_pishock_client_dry_run():
    client = PiShockClient({"username": "u", "api_key": "k", "share_code": "code", "dry_run": True})
    status, text = asyncio.run(client.operate(op=2, intensity=1, duration_s=1))
    assert status == 200
    assert "dry_run" in text
