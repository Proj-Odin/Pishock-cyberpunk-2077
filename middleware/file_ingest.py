from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

from middleware.security import compute_signature


def stream_jsonl(path: Path, poll_interval_s: float = 0.2):
    # Accept JSONL files saved with or without a UTF-8 BOM.
    with path.open("r", encoding="utf-8-sig") as handle:
        while True:
            line = handle.readline()
            if not line:
                time.sleep(poll_interval_s)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"skipping_invalid_jsonl_line: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send JSONL events to local middleware")
    parser.add_argument("--file", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/event")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--poll-interval-s", type=float, default=0.2)
    args = parser.parse_args()

    source_file = Path(args.file)
    if not source_file.exists():
        raise SystemExit(f"file_not_found: {source_file}")

    with httpx.Client(timeout=3.0) as client:
        for event in stream_jsonl(source_file, poll_interval_s=max(0.05, args.poll_interval_s)):
            body = json.dumps(event, separators=(",", ":")).encode("utf-8")
            sig = compute_signature(args.secret, body)
            try:
                resp = client.post(args.url, content=body, headers={"content-type": "application/json", "x-signature": sig})
            except httpx.HTTPError as exc:
                print(f"middleware_post_failed: {exc}", file=sys.stderr)
                time.sleep(0.5)
                continue
            print(resp.status_code, resp.text)


if __name__ == "__main__":
    main()
