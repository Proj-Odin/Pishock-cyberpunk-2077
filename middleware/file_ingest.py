from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx

from middleware.security import compute_signature


def stream_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        while True:
            line = handle.readline()
            if not line:
                time.sleep(0.2)
                continue
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Send JSONL events to local middleware")
    parser.add_argument("--file", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/event")
    parser.add_argument("--secret", required=True)
    args = parser.parse_args()

    for event in stream_jsonl(Path(args.file)):
        body = json.dumps(event, separators=(",", ":")).encode("utf-8")
        sig = compute_signature(args.secret, body)
        with httpx.Client(timeout=3.0) as client:
            resp = client.post(args.url, content=body, headers={"content-type": "application/json", "x-signature": sig})
        print(resp.status_code, resp.text)


if __name__ == "__main__":
    main()
