from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from middleware.security import compute_signature

MARKER = "[PISHOCK_EVT] "


def stream_cet_events(log_path: Path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)

    with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.seek(0, 2)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(0.2)
                continue

            if MARKER not in line:
                continue

            payload = line.split(MARKER, 1)[1].strip()
            if not payload:
                continue

            try:
                yield json.loads(payload)
            except json.JSONDecodeError as exc:
                print(f"[cet_log_ingest] bad JSON after marker: {exc} | payload={payload!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tail CET scripting.log and forward marked events to middleware")
    parser.add_argument("--log", required=True, help="Path to CET scripting.log")
    parser.add_argument("--url", default="http://127.0.0.1:8000/event")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds for middleware POST")
    args = parser.parse_args()

    with httpx.Client(timeout=args.timeout) as client:
        for event in stream_cet_events(Path(args.log)):
            body = json.dumps(event, separators=(",", ":")).encode("utf-8")
            signature = compute_signature(args.secret, body)
            try:
                response = client.post(
                    args.url,
                    content=body,
                    headers={"content-type": "application/json", "x-signature": signature},
                )
                print(response.status_code, response.text)
            except Exception as exc:
                print(f"[cet_log_ingest] post failed: {exc} (check middleware is running on {args.url})")


if __name__ == "__main__":
    main()
