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


class FakeShockerBeepNoIntensity:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def shock(self, duration: int, intensity: int):
        return {"op": "shock", "duration": duration, "intensity": intensity}

    def vibrate(self, duration: int, intensity: int):
        return {"op": "vibrate", "duration": duration, "intensity": intensity}

    def beep(self, duration: int):
        return {"op": "beep", "duration": duration}


class FakeShockerPositionalOnly:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def shock(self, duration: int, intensity: int):
        return {"op": "shock", "duration": duration, "intensity": intensity}

    def vibrate(self, duration: int, intensity: int):
        return {"op": "vibrate", "duration": duration, "intensity": intensity}

    def beep(self, duration: int):
        return {"op": "beep", "duration": duration}


class FakePiShockAPI:
    def __init__(self, username: str, api_key: str):
        self.username = username
        self.api_key = api_key

    def shocker(self, share_code: str, name: str):
        return FakeShockerBeepNoIntensity(username=self.username, api_key=self.api_key, share_code=share_code, name=name)


def test_pishock_client_uses_shocker_library(monkeypatch):
    fake_module = types.SimpleNamespace(Shocker=FakeShocker)
    monkeypatch.setitem(sys.modules, "pishock", fake_module)

    client = PiShockClient({"username": "u", "api_key": "k", "share_code": "code", "name": "n"})

    status, text = asyncio.run(client.operate(op=1, intensity=10, duration_s=1))
    assert status == 200
    assert "vibrate" in text


def test_pishock_client_uses_pishock_api_and_beep_no_intensity(monkeypatch):
    fake_module = types.SimpleNamespace(PiShockAPI=FakePiShockAPI, Shocker=FakeShocker)
    monkeypatch.setitem(sys.modules, "pishock", fake_module)

    client = PiShockClient({"username": "u", "api_key": "k", "share_code": "code", "name": "n"})

    status, text = asyncio.run(client.operate(op=2, intensity=10, duration_s=1))
    assert status == 200
    assert "'op': 'beep'" in text


def test_pishock_client_uses_positional_fallback(monkeypatch):
    class KwargFailsShocker(FakeShockerPositionalOnly):
        def shock(self, *args, **kwargs):
            if kwargs:
                raise TypeError("kwargs unsupported")
            duration, intensity = args
            return super().shock(duration=duration, intensity=intensity)

    fake_module = types.SimpleNamespace(Shocker=KwargFailsShocker)
    monkeypatch.setitem(sys.modules, "pishock", fake_module)

    client = PiShockClient({"username": "u", "api_key": "k", "share_code": "code", "name": "n"})

    status, text = asyncio.run(client.operate(op=0, intensity=10, duration_s=1))
    assert status == 200
    assert "shock" in text


def test_pishock_client_requires_credentials():
    try:
        PiShockClient({"username": "u", "api_key": "k", "share_code": ""})
        raise AssertionError("expected runtime error")
    except RuntimeError as exc:
        assert str(exc) == "pishock_credentials_missing"
