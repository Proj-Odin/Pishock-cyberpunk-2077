from pathlib import Path
import shutil
import uuid

from middleware.file_ingest import stream_jsonl


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
