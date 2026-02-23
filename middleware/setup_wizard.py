from __future__ import annotations

from pathlib import Path

import yaml

from pathlib import Path

TEMPLATE = Path(__file__).with_name("config.example.yaml")
TARGET = Path(__file__).with_name("config.yaml")


def _prompt(default: str, label: str, secret: bool = False) -> str:
    shown = "***" if (secret and default) else default
    raw = input(f"{label} [{shown}]: ").strip()
    return raw if raw else default


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
    enabled_default = bool(enemy_cfg.get("enabled", True))
    enabled_raw = _prompt("yes" if enabled_default else "no", "Enable enemy scaling? (yes/no)").lower()
    enemy_cfg["enabled"] = enabled_raw in {"y", "yes", "true", "1"}
    enemy_cfg["intensity_per_enemy"] = _prompt_float(float(enemy_cfg.get("intensity_per_enemy", 0.1)), "Intensity increase per enemy")
    enemy_cfg["bonus_threshold"] = _prompt_int(int(enemy_cfg.get("bonus_threshold", 3)), "Bonus pulse threshold (enemies per extra pulse)")
    enemy_cfg["bonus_pulse_intensity_ratio"] = _prompt_float(
        float(enemy_cfg.get("bonus_pulse_intensity_ratio", 0.5)),
        "Bonus pulse intensity ratio",
    )
    enemy_cfg["bonus_global_cooldown_ms"] = _prompt_int(
        int(enemy_cfg.get("bonus_global_cooldown_ms", 1200)),
        "Bonus pulse global cooldown (ms)",
    )
    enemy_cfg["min_tick_ms"] = _prompt_int(int(enemy_cfg.get("min_tick_ms", 250)), "Minimum hard-mode cadence (ms)")
    enemy_cfg["tick_reduction_per_enemy_ms"] = _prompt_int(
        int(enemy_cfg.get("tick_reduction_per_enemy_ms", 100)),
        "Cadence reduction per enemy (ms)",
    )
    enemy_cfg["duration_per_enemy_ms"] = _prompt_int(
        int(enemy_cfg.get("duration_per_enemy_ms", 100)),
        "Duration increase per enemy (ms)",
    )

    TARGET.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"\nSaved {TARGET}.")
    if existing:
        print("Updated existing config safely (rerunnable).")
    else:
        print("Created new config.")
def main() -> None:
    if TARGET.exists():
        print("config.yaml already exists")
        return
    TARGET.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    print("Created middleware/config.yaml. Edit credentials and secret before running.")


if __name__ == "__main__":
    main()
