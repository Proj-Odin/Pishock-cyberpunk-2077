from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class EventMapping:
    mode: str
    intensity: int
    duration_ms: int
    cooldown_ms: int


@dataclass
class EnemyTier:
    min_enemies: int
    max_enemies: int | None
    extra_pulses: int


@dataclass
class EnemyScalingConfig:
    enabled: bool = True
    intensity_per_enemy: float = 0.1
    use_logarithmic_intensity: bool = True
    bonus_threshold: int = 3
    bonus_pulse_intensity_ratio: float = 0.5
    bonus_global_cooldown_ms: int = 1200
    min_tick_ms: int = 250
    tick_reduction_per_enemy_ms: int = 100
    duration_per_enemy_ms: int = 100
    max_duration_multiplier: float = 2.0
    combat_combo_enabled: bool = True
    combat_combo_min_enemies: int = 2
    pulse_spacing_ms: int = 120
    tiers: list[EnemyTier] = field(default_factory=list)


@dataclass
class AppConfig:
    hmac_secret: str
    allow_shock: bool
    max_intensity: int
    max_duration_ms: int
    default_cooldown_ms: int
    pishock: dict[str, Any]
    event_mappings: dict[str, EventMapping]
    enemy_scaling: EnemyScalingConfig


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        logger.error("config file not found path=%s", config_path)
        raise RuntimeError(
            f"config_file_not_found: {config_path}. "
            "Copy middleware/config.example.yaml to middleware/config.yaml or run python -m middleware.setup_wizard."
        )

    import yaml

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("config load failed path=%s error_type=%s", config_path, type(exc).__name__)
        raise RuntimeError(f"config_load_failed: {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        logger.error("invalid config path=%s reason=expected_mapping", config_path)
        raise RuntimeError(f"invalid_config: {config_path}: expected a YAML mapping")

    try:
        policy_raw = raw["policy"]
        security_raw = raw["security"]
        default_cooldown_ms = int(policy_raw["default_cooldown_ms"])

        mappings = {
            key: EventMapping(
                mode=value["mode"],
                intensity=int(value["intensity"]),
                duration_ms=int(value["duration_ms"]),
                cooldown_ms=int(value.get("cooldown_ms", default_cooldown_ms)),
            )
            for key, value in raw.get("event_mappings", {}).items()
        }

        enemy_raw = raw.get("enemy_scaling", {})
        tiers = [
            EnemyTier(
                min_enemies=int(t.get("min_enemies", 1)),
                max_enemies=(None if t.get("max_enemies") is None else int(t.get("max_enemies"))),
                extra_pulses=int(t.get("extra_pulses", 0)),
            )
            for t in enemy_raw.get("tiers", [])
        ]

        enemy_scaling = EnemyScalingConfig(
            enabled=_as_bool(enemy_raw.get("enabled", True), default=True),
            intensity_per_enemy=float(enemy_raw.get("intensity_per_enemy", 0.1)),
            use_logarithmic_intensity=_as_bool(enemy_raw.get("use_logarithmic_intensity", True), default=True),
            bonus_threshold=int(enemy_raw.get("bonus_threshold", 3)),
            bonus_pulse_intensity_ratio=float(enemy_raw.get("bonus_pulse_intensity_ratio", 0.5)),
            bonus_global_cooldown_ms=int(enemy_raw.get("bonus_global_cooldown_ms", 1200)),
            min_tick_ms=int(enemy_raw.get("min_tick_ms", 250)),
            tick_reduction_per_enemy_ms=int(enemy_raw.get("tick_reduction_per_enemy_ms", 100)),
            duration_per_enemy_ms=int(enemy_raw.get("duration_per_enemy_ms", 100)),
            max_duration_multiplier=float(enemy_raw.get("max_duration_multiplier", 2.0)),
            combat_combo_enabled=_as_bool(enemy_raw.get("combat_combo_enabled", True), default=True),
            combat_combo_min_enemies=int(enemy_raw.get("combat_combo_min_enemies", 2)),
            pulse_spacing_ms=int(enemy_raw.get("pulse_spacing_ms", 120)),
            tiers=tiers,
        )

        pishock = dict(raw.get("pishock", {}) or {})
        pishock["dry_run"] = _as_bool(pishock.get("dry_run", True), default=True)

        return AppConfig(
            hmac_secret=str(security_raw["hmac_secret"]),
            allow_shock=_as_bool(policy_raw.get("allow_shock", False), default=False),
            max_intensity=int(policy_raw["max_intensity"]),
            max_duration_ms=int(policy_raw["max_duration_ms"]),
            default_cooldown_ms=default_cooldown_ms,
            pishock=pishock,
            event_mappings=mappings,
            enemy_scaling=enemy_scaling,
        )
    except KeyError as exc:
        logger.error("invalid config missing key path=%s key=%s", config_path, exc.args[0])
        raise RuntimeError(f"invalid_config_missing_key: {config_path}: {exc.args[0]}") from exc
    except (TypeError, ValueError) as exc:
        logger.error("invalid config path=%s error_type=%s", config_path, type(exc).__name__)
        raise RuntimeError(f"invalid_config: {config_path}: {exc}") from exc
