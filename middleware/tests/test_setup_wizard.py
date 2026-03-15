from pathlib import Path
import shutil
import uuid

from middleware.setup_wizard import _validate_and_create_event_path


def test_validate_and_create_event_path() -> None:
    base = Path(".tmp_test_setup_wizard") / str(uuid.uuid4())
    try:
        target = base / "mods" / "pishock_bridge" / "events.jsonl"
        created = _validate_and_create_event_path(str(target))
        assert created == target
        assert created.exists()
        assert created.is_file()
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_validate_and_create_event_path_requires_jsonl_suffix() -> None:
    base = Path(".tmp_test_setup_wizard") / str(uuid.uuid4())
    try:
        target = base / "mods" / "pishock_bridge" / "events.txt"
        try:
            _validate_and_create_event_path(str(target))
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
    finally:
        shutil.rmtree(base, ignore_errors=True)
