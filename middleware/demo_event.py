from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import httpx

from middleware.config import load_config
from middleware.security import compute_signature

BASE_URL_ENV = "PISHOCK_BASE_URL"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def _resolve_secret(secret: str | None, config_path: str | None) -> str:
    if secret:
        return secret

    if config_path:
        path = Path(config_path)
    else:
        default = Path(__file__).with_name("config.yaml")
        path = default if default.exists() else Path(__file__).with_name("config.example.yaml")

    return load_config(path).hmac_secret


def _resolve_base_url(cli_base_url: str | None) -> str:
    return (cli_base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send one signed demo event to the middleware API")
    parser.add_argument(
        "--base-url",
        "--url",
        dest="base_url",
        default=None,
        help=f"Base middleware URL (default: {DEFAULT_BASE_URL}; env: {BASE_URL_ENV})",
    )
    parser.add_argument("--session-id", default="demo-run", help="Session id used for arm/event")
    parser.add_argument("--event-type", default="player_damaged", help="Event type to send")
    parser.add_argument("--context-json", default='{"damage":12}', help="JSON object string for context")
    parser.add_argument("--ts-ms", type=int, default=0, help="Override event timestamp in ms (default: now)")
    parser.add_argument("--secret", default="", help="HMAC secret; falls back to config if omitted")
    parser.add_argument("--config", default="", help="Optional path to config YAML for secret fallback")
    parser.add_argument("--skip-arm", action="store_true", help="Skip POST /arm/{session_id}")
    parser.add_argument("--payload-unarmed", action="store_true", help="Send payload with armed=false")
    parser.add_argument("--timeout-s", type=float, default=3.0)
    parser.add_argument("--debug", action="store_true", help="Show tracebacks for connection/debug failures")
    return parser


def _connection_help(base_url: str) -> str:
    return (
        f"Could not connect to middleware at {base_url}.\n\n"
        "Start the middleware in another PowerShell window:\n\n"
        '    $env:PISHOCK_RUNTIME_MODE="test"\n'
        "    python -m middleware.run\n\n"
        "Verify health:\n\n"
        f"    Invoke-RestMethod {base_url}/health\n\n"
        "Then retry this demo command."
    )


def _health_line(status_code: int, health_payload: dict) -> str:
    def format_value(value: object) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)

    runtime_mode = format_value(health_payload.get("runtime_mode", "unknown"))
    dry_run_effective = format_value(health_payload.get("dry_run_effective", "unknown"))
    pishock_client_mode = format_value(health_payload.get("pishock_client_mode", "unknown"))
    return (
        f"health_status={status_code} runtime_mode={runtime_mode} "
        f"dry_run_effective={dry_run_effective} pishock_client_mode={pishock_client_mode}"
    )


def _event_response_hint(response_text: str, runtime_mode: str | None = None) -> str:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""

    if payload.get("accepted") is False and payload.get("reason") == "pishock_operate_failed":
        if runtime_mode == "beep":
            return (
                "You are in beep mode. Beep mode may use the real PiShock API for beep-only manual tests.\n"
                "This requires python-pishock, valid config, API access, and reachable hardware.\n"
                "For a no-hardware dry run, restart the middleware with:\n"
                '    $env:PISHOCK_RUNTIME_MODE="test"\n'
                "    python -m middleware.run"
            )
        return (
            "The event reached the middleware, but the PiShock operation failed.\n\n"
            "If runtime_mode=test:\n"
            "  This is a bug. Test mode should use dry-run and should not call PiShock.\n\n"
            "If runtime_mode=beep:\n"
            "  Beep mode requires the python-pishock dependency, valid PiShock config, working API access, and reachable hardware.\n"
            "  Install/check the PiShock dependency and verify credentials before retrying beep mode.\n\n"
            "If runtime_mode=live:\n"
            "  Check PiShock dependency, credentials, share code, device availability, API availability, and logs."
        )
    if payload.get("accepted") is True and "dry_run" in str(payload.get("pishock_response", "")):
        return "Dry-run/mock PiShock operation completed; no real PiShock API/device operation occurred."
    return ""


def _pishock_failure_exit_code(response_text: str) -> int | None:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and payload.get("accepted") is False and payload.get("reason") == "pishock_operate_failed":
        return 4
    return None


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        context = json.loads(args.context_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid_context_json: {exc}") from exc
    if not isinstance(context, dict):
        raise SystemExit("invalid_context_json: expected a JSON object")

    secret = _resolve_secret(args.secret or None, args.config or None)
    ts_ms = args.ts_ms if args.ts_ms > 0 else int(time.time() * 1000)
    payload = {
        "event_type": args.event_type,
        "ts_ms": ts_ms,
        "session_id": args.session_id,
        "armed": not args.payload_unarmed,
        "context": context,
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = compute_signature(secret, body)
    base_url = _resolve_base_url(args.base_url)

    with httpx.Client(timeout=max(0.5, args.timeout_s)) as client:
        try:
            health_resp = client.get(f"{base_url}/health")
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError):
            if args.debug:
                raise
            print(_connection_help(base_url))
            raise SystemExit(2) from None
        try:
            health_payload = health_resp.json()
        except ValueError:
            health_payload = {}
        if not isinstance(health_payload, dict):
            health_payload = {}
        print(_health_line(health_resp.status_code, health_payload))
        runtime_mode = str(health_payload.get("runtime_mode", "unknown"))

        if not args.skip_arm:
            arm_resp = client.post(f"{base_url}/arm/{args.session_id}")
            print(f"arm_status={arm_resp.status_code} arm_response={arm_resp.text}")

        event_resp = client.post(
            f"{base_url}/event",
            content=body,
            headers={"content-type": "application/json", "x-signature": signature},
        )
        print(f"event_status={event_resp.status_code} event_response={event_resp.text}")
        hint = _event_response_hint(event_resp.text, runtime_mode=runtime_mode)
        if hint:
            print(hint)

        failure_exit_code = _pishock_failure_exit_code(event_resp.text)
        if failure_exit_code is not None:
            raise SystemExit(failure_exit_code)

        if event_resp.status_code >= 400:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
