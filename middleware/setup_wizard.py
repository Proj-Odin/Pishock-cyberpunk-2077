from __future__ import annotations

from pathlib import Path

import yaml

TEMPLATE = Path(__file__).with_name("config.example.yaml")
TARGET = Path(__file__).with_name("config.yaml")


def _prompt(default: str, label: str, secret: bool = False) -> str:
    shown = "***" if (secret and default) else default
    raw = input(f"{label} [{shown}]: ").strip()
    return raw if raw else default


def _prompt_bool(default: bool, label: str) -> bool:
    default_text = "yes" if default else "no"
    while True:
        raw = input(f"{label} [{default_text}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "true", "1"}:
            return True
        if raw in {"n", "no", "false", "0"}:
            return False
        print("Please enter yes or no.")


def _prompt_int(default: int, label: str) -> int:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid integer.")


def _prompt_float(default: float, label: str) -> float:
    while True:
        raw = input(f"{label} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            print("Please enter a valid number.")


def _merge_defaults(template: dict, existing: dict | None) -> dict:
    if not existing:
        return template
    merged = dict(template)
    for key, value in existing.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_defaults(merged[key], value)
        else:
            merged[key] = value
    return merged


def _configure_tiers(current_tiers: list[dict]) -> list[dict]:
    if not _prompt_bool(True, "Customize enemy tiers now?"):
        return current_tiers

    tiers: list[dict] = []
    print("Add tier rows. Example: 3-5 enemies => 1 extra pulse.")
    while True:
        min_enemies = _prompt_int(1, "Tier min enemies")
        max_raw = _prompt("", "Tier max enemies (blank for no upper limit)")
        max_enemies = int(max_raw) if max_raw else None
        extra_pulses = _prompt_int(1, "Tier extra pulses")
        tiers.append({"min_enemies": min_enemies, "max_enemies": max_enemies, "extra_pulses": extra_pulses})
        if not _prompt_bool(False, "Add another tier?"):
            break
    return tiers


def main() -> None:
    template = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    existing = yaml.safe_load(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else None
    config = _merge_defaults(template, existing)

    print("PiShock setup wizard (safe to re-run)")
    print("Press Enter to keep current values shown in brackets.")

    pishock_cfg = config.setdefault("pishock", {})
    pishock_cfg["username"] = _prompt(str(pishock_cfg.get("username", "")), "PiShock username")
    pishock_cfg["api_key"] = _prompt(str(pishock_cfg.get("api_key", "")), "PiShock API key", secret=True)
    pishock_cfg["share_code"] = _prompt(str(pishock_cfg.get("share_code", "")), "PiShock share code")
    pishock_cfg["name"] = _prompt(str(pishock_cfg.get("name", "CyberpunkBridge")), "Sender name")

    if not pishock_cfg["username"] or not pishock_cfg["api_key"] or not pishock_cfg["share_code"]:
        raise SystemExit("username, api_key, and share_code are required")

    enemy_cfg = config.setdefault("enemy_scaling", {})
    print("\nEnemy scaling setup (hard mode):")
    enemy_cfg["enabled"] = _prompt_bool(bool(enemy_cfg.get("enabled", True)), "Enable enemy scaling?")
    enemy_cfg["intensity_per_enemy"] = _prompt_float(float(enemy_cfg.get("intensity_per_enemy", 0.12)), "Intensity increase per enemy")
    enemy_cfg["use_logarithmic_intensity"] = _prompt_bool(
        bool(enemy_cfg.get("use_logarithmic_intensity", False)),
        "Use logarithmic diminishing returns?",
    )
    enemy_cfg["bonus_threshold"] = _prompt_int(int(enemy_cfg.get("bonus_threshold", 2)), "Enemies per extra threshold pulse")
    enemy_cfg["bonus_pulse_intensity_ratio"] = _prompt_float(
        float(enemy_cfg.get("bonus_pulse_intensity_ratio", 0.6)),
        "Bonus pulse intensity ratio",
    )
    enemy_cfg["bonus_global_cooldown_ms"] = _prompt_int(
        int(enemy_cfg.get("bonus_global_cooldown_ms", 700)),
        "Bonus pulse global cooldown (ms)",
    )
    enemy_cfg["min_tick_ms"] = _prompt_int(int(enemy_cfg.get("min_tick_ms", 250)), "Minimum hard-mode cadence (ms)")
    enemy_cfg["tick_reduction_per_enemy_ms"] = _prompt_int(
        int(enemy_cfg.get("tick_reduction_per_enemy_ms", 100)),
        "Cadence reduction per enemy (ms)",
    )
    enemy_cfg["duration_per_enemy_ms"] = _prompt_int(
        int(enemy_cfg.get("duration_per_enemy_ms", 120)),
        "Duration increase per enemy (ms)",
    )
    enemy_cfg["max_duration_multiplier"] = _prompt_float(
        float(enemy_cfg.get("max_duration_multiplier", 2.0)),
        "Max duration multiplier",
    )
    enemy_cfg["combat_combo_enabled"] = _prompt_bool(
        bool(enemy_cfg.get("combat_combo_enabled", True)),
        "Enable in-combat combo pulses?",
    )
    enemy_cfg["combat_combo_min_enemies"] = _prompt_int(
        int(enemy_cfg.get("combat_combo_min_enemies", 2)),
        "Combat combo minimum enemies",
    )
    enemy_cfg["pulse_spacing_ms"] = _prompt_int(int(enemy_cfg.get("pulse_spacing_ms", 120)), "Bonus pulse spacing (ms)")
    enemy_cfg["tiers"] = _configure_tiers(enemy_cfg.get("tiers", []))

    TARGET.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"\nSaved {TARGET}.")
    print("Re-run this wizard any time; existing values are preserved unless changed.")


if __name__ == "__main__":
    main()
