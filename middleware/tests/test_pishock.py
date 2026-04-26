import asyncio
import sys
import types

import middleware.pishock as pishock_module
from middleware.pishock import (
    BeepOnlyPiShockClient,
    DryRunPiShockClient,
    PiShockClient,
    build_pishock_client,
    effective_dry_run,
)
from middleware.runtime_mode import RuntimeMode


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


class FakeOperateClient:
    def __init__(self):
        self.calls: list[tuple[int, int, int]] = []

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        self.calls.append((op, intensity, duration_s))
        return 200, f"fake op={op}"


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


def test_build_pishock_client_defaults_to_dry_run_without_credentials():
    client = build_pishock_client({})
    assert isinstance(client, DryRunPiShockClient)
    assert client.client_mode == "dry_run"

    status, text = asyncio.run(client.operate(op=1, intensity=10, duration_s=1))

    assert status == 200
    assert "dry_run" in text


def test_build_pishock_client_requires_credentials_when_dry_run_disabled():
    try:
        build_pishock_client(
            {"dry_run": False, "username": "", "api_key": "", "share_code": ""},
            mode=RuntimeMode.LIVE,
        )
        raise AssertionError("expected runtime error")
    except RuntimeError as exc:
        assert str(exc) == "pishock_credentials_missing"


def test_test_mode_never_calls_real_pishock_client():
    client = build_pishock_client(
        {"dry_run": False, "username": "", "api_key": "", "share_code": ""},
        mode=RuntimeMode.TEST,
    )
    assert isinstance(client, DryRunPiShockClient)

    status, text = asyncio.run(client.operate(op=0, intensity=10, duration_s=1))

    assert status == 200
    assert "dry_run" in text


def test_test_mode_never_instantiates_real_pishock_client(monkeypatch):
    def fail_real_client(_config):
        raise AssertionError("real client should not be instantiated in test mode")

    monkeypatch.setattr(pishock_module, "PiShockClient", fail_real_client)

    client = pishock_module.build_pishock_client(
        {"dry_run": False, "username": "u", "api_key": "k", "share_code": "code"},
        mode=RuntimeMode.TEST,
    )

    assert isinstance(client, DryRunPiShockClient)


def test_dry_run_true_never_instantiates_real_pishock_client(monkeypatch):
    def fail_real_client(_config):
        raise AssertionError("real client should not be instantiated while dry_run is true")

    monkeypatch.setattr(pishock_module, "PiShockClient", fail_real_client)

    client = pishock_module.build_pishock_client(
        {"dry_run": True, "username": "u", "api_key": "k", "share_code": "code"},
        mode=RuntimeMode.LIVE,
    )

    assert isinstance(client, DryRunPiShockClient)


def test_effective_dry_run_rules():
    assert effective_dry_run({"dry_run": False}, RuntimeMode.TEST) is True
    assert effective_dry_run({"dry_run": True}, RuntimeMode.BEEP) is True
    assert effective_dry_run({"dry_run": False}, RuntimeMode.BEEP) is False
    assert effective_dry_run({"dry_run": True}, RuntimeMode.LIVE) is True
    assert effective_dry_run({"dry_run": False}, RuntimeMode.LIVE) is False


def test_live_mode_accepts_string_false_for_dry_run():
    client = build_pishock_client(
        {"dry_run": "false", "username": "u", "api_key": "k", "share_code": "code"},
        mode=RuntimeMode.LIVE,
    )
    assert isinstance(client, PiShockClient)
    assert client.client_mode == "live"


def test_build_pishock_client_wraps_real_client_in_beep_mode():
    client = build_pishock_client(
        {"dry_run": False, "username": "u", "api_key": "k", "share_code": "code", "name": "n"},
        mode=RuntimeMode.BEEP,
    )

    assert isinstance(client, BeepOnlyPiShockClient)
    assert client.client_mode == "beep_only"


def test_build_pishock_client_wraps_dry_run_in_beep_mode():
    client = build_pishock_client(
        {"dry_run": True, "username": "", "api_key": "", "share_code": ""},
        mode=RuntimeMode.BEEP,
    )

    assert isinstance(client, BeepOnlyPiShockClient)
    assert isinstance(client.real_client, DryRunPiShockClient)


def test_beep_mode_allows_beep_with_fake_client():
    fake = FakeOperateClient()
    client = BeepOnlyPiShockClient(fake)
    status, text = asyncio.run(client.operate(op=2, intensity=1, duration_s=1))

    assert status == 200
    assert text == "fake op=2"
    assert fake.calls == [(2, 1, 1)]


def test_beep_mode_blocks_vibrate_with_fake_client():
    fake = FakeOperateClient()
    client = BeepOnlyPiShockClient(fake)

    try:
        asyncio.run(client.operate(op=1, intensity=1, duration_s=1))
        raise AssertionError("expected runtime error")
    except RuntimeError as exc:
        assert str(exc) == "runtime_mode_beep_blocks_non_beep_operation"
    assert fake.calls == []


def test_beep_mode_blocks_shock_with_fake_client():
    fake = FakeOperateClient()
    client = BeepOnlyPiShockClient(fake)

    try:
        asyncio.run(client.operate(op=0, intensity=1, duration_s=1))
        raise AssertionError("expected runtime error")
    except RuntimeError as exc:
        assert str(exc) == "runtime_mode_beep_blocks_non_beep_operation"
    assert fake.calls == []
