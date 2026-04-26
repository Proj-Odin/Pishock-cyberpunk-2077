from pathlib import Path
import shutil
import uuid

import httpx
import pytest

import middleware.demo_event as demo_event
from middleware.demo_event import _build_parser, _event_response_hint, _resolve_base_url, _resolve_secret


def test_resolve_secret_prefers_explicit_value() -> None:
    assert _resolve_secret("direct-secret", None) == "direct-secret"


def test_resolve_secret_loads_from_config_path() -> None:
    base = Path(".tmp_test_demo_event") / str(uuid.uuid4())
    try:
        base.mkdir(parents=True, exist_ok=True)
        config_path = base / "config.yaml"
        template = Path("middleware/config.example.yaml").read_text(encoding="utf-8")
        config_path.write_text(template.replace("change-me", "secret-from-config", 1), encoding="utf-8")
        assert _resolve_secret(None, str(config_path)) == "secret-from-config"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_base_url_aliases_parse() -> None:
    parser = _build_parser()

    assert parser.parse_args(["--url", "http://127.0.0.1:9000"]).base_url == "http://127.0.0.1:9000"
    assert parser.parse_args(["--base-url", "http://127.0.0.1:9001"]).base_url == "http://127.0.0.1:9001"


def test_cli_base_url_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("PISHOCK_BASE_URL", "http://env-host:8000")

    assert _resolve_base_url("http://cli-host:9000") == "http://cli-host:9000"
    assert _resolve_base_url(None) == "http://env-host:8000"


def test_event_response_hint_explains_pishock_failure() -> None:
    hint = _event_response_hint('{"accepted":false,"reason":"pishock_operate_failed"}')

    assert "PiShock operation failed" in hint
    assert "runtime_mode=test" in hint
    assert "runtime_mode=beep" in hint
    assert "runtime_mode=live" in hint


def test_event_response_hint_explains_dry_run_success() -> None:
    hint = _event_response_hint('{"accepted":true,"pishock_response":"dry_run op=beep"}')

    assert "Dry-run/mock" in hint
    assert "no real PiShock API/device operation" in hint


def test_main_handles_middleware_unavailable_with_friendly_message(monkeypatch, capsys) -> None:
    class UnavailableClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url: str):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(demo_event.httpx, "Client", UnavailableClient)

    with pytest.raises(SystemExit) as exc:
        demo_event.main(["--secret", "s"])

    assert exc.value.code == 2
    output = capsys.readouterr().out
    assert "Could not connect to middleware at http://127.0.0.1:8000." in output
    assert '$env:PISHOCK_RUNTIME_MODE="test"' in output
    assert "python -m middleware.run" in output
    assert "Invoke-RestMethod http://127.0.0.1:8000/health" in output


def test_main_health_check_prints_runtime_mode(monkeypatch, capsys) -> None:
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url: str):
            assert url == "http://127.0.0.1:8000/health"
            return httpx.Response(
                200,
                json={"runtime_mode": "test", "dry_run_effective": True, "pishock_client_mode": "dry_run"},
            )

        def post(self, url: str, **_kwargs):
            assert url == "http://127.0.0.1:8000/event"
            return httpx.Response(
                200,
                json={
                    "accepted": True,
                    "reason": "ok",
                    "pishock_response": "dry_run op=beep intensity=1 duration_s=1",
                },
            )

    monkeypatch.setattr(demo_event.httpx, "Client", FakeClient)

    demo_event.main(["--secret", "s", "--skip-arm", "--event-type", "player_healed", "--context-json", "{}"])

    output = capsys.readouterr().out
    assert "health_status=200 runtime_mode=test dry_run_effective=true pishock_client_mode=dry_run" in output
    assert "Dry-run/mock PiShock operation completed" in output


def test_main_preflights_health_before_arm_and_event(monkeypatch) -> None:
    calls: list[str] = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, url: str):
            calls.append(url)
            return httpx.Response(
                200,
                json={"runtime_mode": "test", "dry_run_effective": True, "pishock_client_mode": "dry_run"},
            )

        def post(self, url: str, **_kwargs):
            calls.append(url)
            if url.endswith("/arm/demo-run"):
                return httpx.Response(200, json={"session_id": "demo-run", "armed": True})
            return httpx.Response(200, json={"accepted": True, "reason": "ok", "pishock_response": "dry_run op=beep"})

    monkeypatch.setattr(demo_event.httpx, "Client", FakeClient)

    demo_event.main(["--secret", "s", "--event-type", "player_healed", "--context-json", "{}"])

    assert calls == [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/arm/demo-run",
        "http://127.0.0.1:8000/event",
    ]


def test_main_pishock_operate_failed_prints_guidance_and_exits_4(monkeypatch, capsys) -> None:
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def get(self, _url: str):
            return httpx.Response(
                200,
                json={"runtime_mode": "beep", "dry_run_effective": False, "pishock_client_mode": "beep_only"},
            )

        def post(self, url: str, **_kwargs):
            assert url == "http://127.0.0.1:8000/event"
            return httpx.Response(
                200,
                json={
                    "accepted": False,
                    "reason": "pishock_operate_failed",
                    "error_code": "python_pishock_not_installed",
                },
            )

    monkeypatch.setattr(demo_event.httpx, "Client", FakeClient)

    with pytest.raises(SystemExit) as exc:
        demo_event.main(["--secret", "s", "--skip-arm", "--event-type", "player_healed", "--context-json", "{}"])

    assert exc.value.code == 4
    output = capsys.readouterr().out
    assert "You are in beep mode." in output
    assert "python-pishock" in output
    assert '$env:PISHOCK_RUNTIME_MODE="test"' in output
