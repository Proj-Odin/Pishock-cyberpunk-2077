import json
from pathlib import Path
import shutil
import uuid

from middleware.file_ingest import encode_signed_event, stream_jsonl
from middleware.security import compute_signature


def test_stream_jsonl_skips_invalid_line_and_yields_valid_json() -> None:
    base = Path(".tmp_test_file_ingest") / str(uuid.uuid4())
    try:
        base.mkdir(parents=True, exist_ok=True)
        source = base / "events.jsonl"
        source.write_text('{"bad"\n{"event_type":"player_damaged"}\n', encoding="utf-8")

        generator = stream_jsonl(source, poll_interval_s=0.01)
        event = next(generator)
        assert event["event_type"] == "player_damaged"
        generator.close()
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_stream_jsonl_accepts_utf8_bom() -> None:
    base = Path(".tmp_test_file_ingest") / str(uuid.uuid4())
    try:
        base.mkdir(parents=True, exist_ok=True)
        source = base / "events.jsonl"
        source.write_text('{"event_type":"player_hard_mode_tick"}\n', encoding="utf-8-sig")

        generator = stream_jsonl(source, poll_interval_s=0.01)
        event = next(generator)
        assert event["event_type"] == "player_hard_mode_tick"
        generator.close()
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_encode_signed_event_uses_compact_json_body_for_hmac() -> None:
    event = {"event_type": "player_damaged", "ts_ms": 1, "session_id": "s1", "armed": True, "context": {"damage": 12}}
    body, signature = encode_signed_event(event, "secret")

    assert body == json.dumps(event, separators=(",", ":")).encode("utf-8")
    assert signature == compute_signature("secret", body)
