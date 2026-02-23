from pathlib import Path

from middleware.setup_wizard import _validate_and_create_event_path


def test_validate_and_create_event_path(tmp_path: Path) -> None:
    target = tmp_path / "mods" / "pishock_bridge" / "events.jsonl"
    created = _validate_and_create_event_path(str(target))
    assert created == target
    assert created.exists()
    assert created.is_file()
