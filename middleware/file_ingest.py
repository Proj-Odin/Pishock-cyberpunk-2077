from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import httpx

from middleware.logging_config import configure_logging
from middleware.security import compute_signature

logger = logging.getLogger(__name__)


def encode_signed_event(event: dict, secret: str) -> tuple[bytes, str]:
    body = json.dumps(event, separators=(",", ":")).encode("utf-8")
    return body, compute_signature(secret, body)


def stream_jsonl(path: Path, poll_interval_s: float = 0.2):
    # Accept JSONL files saved with or without a UTF-8 BOM.
    with path.open("r", encoding="utf-8-sig") as handle:
        line_number = 0
        while True:
            line = handle.readline()
            if not line:
                time.sleep(poll_interval_s)
                continue
            line_number += 1
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("skipping invalid JSONL line path=%s line=%s error=%s", path, line_number, exc)
                print(f"skipping_invalid_jsonl_line line={line_number}: {exc}", file=sys.stderr)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Send JSONL events to local middleware")
    parser.add_argument("--file", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000/event")
    parser.add_argument("--secret", required=True)
    parser.add_argument("--poll-interval-s", type=float, default=0.2)
    args = parser.parse_args()

    source_file = Path(args.file)
    if not source_file.exists():
        logger.error("file ingest source file not found path=%s", source_file)
        raise SystemExit(f"file_not_found: {source_file}")

    logger.info("file ingest starting source=%s target_url=%s", source_file, args.url)
    with httpx.Client(timeout=3.0) as client:
        for event in stream_jsonl(source_file, poll_interval_s=max(0.05, args.poll_interval_s)):
            body, sig = encode_signed_event(event, args.secret)
            try:
                resp = client.post(args.url, content=body, headers={"content-type": "application/json", "x-signature": sig})
            except httpx.HTTPError as exc:
                logger.error("middleware post failed target_url=%s error_type=%s", args.url, type(exc).__name__)
                print(f"middleware_post_failed: {exc}", file=sys.stderr)
                time.sleep(0.5)
                continue
            reason = ""
            try:
                payload = resp.json()
                if isinstance(payload, dict):
                    reason = str(payload.get("reason", payload.get("detail", "")))
            except json.JSONDecodeError:
                reason = ""
            logger.info("middleware response status=%s reason=%s", resp.status_code, reason)
            print(resp.status_code, resp.text)


if __name__ == "__main__":
    main()
