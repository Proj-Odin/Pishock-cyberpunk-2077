from pathlib import Path
import shutil
import uuid

from middleware.config import load_config


def test_load_config_parses_string_booleans_safely() -> None:
    base = Path(".tmp_test_config") / str(uuid.uuid4())
    try:
        base.mkdir(parents=True, exist_ok=True)
        config_path = base / "config.yaml"
        config_path.write_text(
            """
security:
  hmac_secret: test-secret
policy:
  allow_shock: "false"
  max_intensity: 20
  max_duration_ms: 1500
  default_cooldown_ms: 1000
pishock:
  dry_run: "false"
event_mappings:
  player_healed:
    mode: beep
    intensity: 1
    duration_ms: 500
enemy_scaling:
  enabled: "false"
""",
            encoding="utf-8",
        )

        config = load_config(config_path)

        assert config.allow_shock is False
        assert config.pishock["dry_run"] is False
        assert config.enemy_scaling.enabled is False
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_load_config_missing_file_has_setup_hint() -> None:
    base = Path(".tmp_test_config") / str(uuid.uuid4())
    try:
        load_config(base / "missing.yaml")
        raise AssertionError("expected runtime error")
    except RuntimeError as exc:
        message = str(exc)
        assert "config_file_not_found" in message
        assert "python -m middleware.setup_wizard" in message
