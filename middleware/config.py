from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class EventMapping:
    mode: str
    intensity: int
    duration_ms: int
    cooldown_ms: int


@dataclass
class AppConfig:
    hmac_secret: str
    allow_shock: bool
    max_intensity: int
    max_duration_ms: int
    default_cooldown_ms: int
    pishock: dict[str, Any]
    event_mappings: dict[str, EventMapping]


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    mappings = {
        key: EventMapping(
            mode=value["mode"],
            intensity=int(value["intensity"]),
            duration_ms=int(value["duration_ms"]),
            cooldown_ms=int(value.get("cooldown_ms", raw["policy"]["default_cooldown_ms"])),
        )
        for key, value in raw.get("event_mappings", {}).items()
    }

    return AppConfig(
        hmac_secret=raw["security"]["hmac_secret"],
        allow_shock=bool(raw["policy"].get("allow_shock", False)),
        max_intensity=int(raw["policy"]["max_intensity"]),
        max_duration_ms=int(raw["policy"]["max_duration_ms"]),
        default_cooldown_ms=int(raw["policy"]["default_cooldown_ms"]),
        pishock=raw.get("pishock", {}),
        event_mappings=mappings,
    )
