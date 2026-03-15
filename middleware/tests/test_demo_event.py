from pathlib import Path
import shutil
import uuid

from middleware.demo_event import _resolve_secret


def test_resolve_secret_prefers_explicit_value() -> None:
    assert _resolve_secret("direct-secret", None) == "direct-secret"


def test_resolve_secret_loads_from_config_path() -> None:
    base = Path(".tmp_test_demo_event") / str(uuid.uuid4())
    try:
        base.mkdir(parents=True, exist_ok=True)
        config_path = base / "config.yaml"
        template = Path("middleware/config.example.yaml").read_text(encoding="utf-8")
        config_path.write_text(template.replace("change-me", "secret-from-config", 1), encoding="utf-8")
        assert _resolve_secret(None, str(config_path)) == "secret-from-config"
    finally:
        shutil.rmtree(base, ignore_errors=True)
