from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from middleware.config import load_config
from middleware.security import compute_signature


def _resolve_secret(secret: str | None, config_path: str | None) -> str:
    if secret:
        return secret

    if config_path:
        path = Path(config_path)
    else:
        default = Path(__file__).with_name("config.yaml")
        path = default if default.exists() else Path(__file__).with_name("config.example.yaml")

    return load_config(path).hmac_secret


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one signed demo event to the middleware API")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base middleware URL")
    parser.add_argument("--session-id", default="demo-run", help="Session id used for arm/event")
    parser.add_argument("--event-type", default="player_damaged", help="Event type to send")
    parser.add_argument("--context-json", default='{"damage":12}', help="JSON object string for context")
    parser.add_argument("--ts-ms", type=int, default=0, help="Override event timestamp in ms (default: now)")
    parser.add_argument("--secret", default="", help="HMAC secret; falls back to config if omitted")
    parser.add_argument("--config", default="", help="Optional path to config YAML for secret fallback")
    parser.add_argument("--skip-arm", action="store_true", help="Skip POST /arm/{session_id}")
    parser.add_argument("--payload-unarmed", action="store_true", help="Send payload with armed=false")
    parser.add_argument("--timeout-s", type=float, default=3.0)
    args = parser.parse_args()

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
    base_url = args.url.rstrip("/")

    with httpx.Client(timeout=max(0.5, args.timeout_s)) as client:
        if not args.skip_arm:
            arm_resp = client.post(f"{base_url}/arm/{args.session_id}")
            print(f"arm_status={arm_resp.status_code} arm_response={arm_resp.text}")

        event_resp = client.post(
            f"{base_url}/event",
            content=body,
            headers={"content-type": "application/json", "x-signature": signature},
        )
        print(f"event_status={event_resp.status_code} event_response={event_resp.text}")

        if event_resp.status_code >= 400:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
