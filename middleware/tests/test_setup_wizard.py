from pathlib import Path
import shutil
import uuid

from middleware.setup_wizard import _merge_defaults, _validate_and_create_event_path


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


def test_merge_defaults_preserves_existing_nested_values() -> None:
    template = {
        "policy": {"allow_shock": False, "max_intensity": 20},
        "pishock": {"dry_run": True, "username": ""},
        "new_section": {"enabled": True},
    }
    existing = {
        "policy": {"max_intensity": 10},
        "pishock": {"username": "kept"},
    }

    merged = _merge_defaults(template, existing)

    assert merged["policy"]["allow_shock"] is False
    assert merged["policy"]["max_intensity"] == 10
    assert merged["pishock"]["dry_run"] is True
    assert merged["pishock"]["username"] == "kept"
    assert merged["new_section"]["enabled"] is True
