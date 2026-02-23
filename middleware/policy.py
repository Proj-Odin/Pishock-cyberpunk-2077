from __future__ import annotations

import math
from dataclasses import dataclass
from time import monotonic
from typing import Any

from middleware.config import AppConfig, EnemyTier, EventMapping


MODE_TO_OP = {"shock": 0, "vibrate": 1, "beep": 2, "hard": 0}


@dataclass
class Decision:
    allowed: bool
    reason: str
    op: int | None = None
    intensity: int | None = None
    duration_s: int | None = None
    bonus_pulses: int = 0
    bonus_intensity_ratio: float = 0.5
    pulse_spacing_ms: int = 120


@dataclass
class HardModeState:
    max_hp: int
    initial_missing_hp: int
    current_enemy_count: int = 0


class PolicyEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self._cooldowns: dict[tuple[str, str], float] = {}
        self._bonus_cooldowns: dict[tuple[str, str], float] = {}
        self._hard_mode_states: dict[str, HardModeState] = {}

    def evaluate(self, session_id: str, event_type: str, armed: bool, context: dict[str, Any] | None = None) -> Decision:
        mapping: EventMapping | None = self.config.event_mappings.get(event_type)
        if mapping is None:
            return Decision(False, "event_not_mapped")
        if not armed:
            return Decision(False, "session_not_armed")
        if mapping.mode in {"shock", "hard"} and not self.config.allow_shock:
            return Decision(False, "shock_disabled")

        context = context or {}
        if mapping.mode == "hard":
            return self._evaluate_hard_mode(session_id, mapping, context)

        if not self._consume_cooldown(session_id, event_type, mapping.cooldown_ms):
            return Decision(False, "cooldown_active")

        intensity = max(1, min(mapping.intensity, self.config.max_intensity))
        duration_ms = max(100, min(mapping.duration_ms, self.config.max_duration_ms))
        duration_s = max(1, round(duration_ms / 1000))

        return Decision(True, "ok", op=MODE_TO_OP[mapping.mode], intensity=intensity, duration_s=duration_s)

    def _consume_cooldown(self, session_id: str, event_type: str, cooldown_ms: int) -> bool:
        cooldown_key = (session_id, event_type)
        now = monotonic()
        next_ok = self._cooldowns.get(cooldown_key, 0.0)
        if now < next_ok:
            return False
        self._cooldowns[cooldown_key] = now + (cooldown_ms / 1000)
        return True

    def _consume_bonus_cooldown(self, session_id: str, event_type: str, cooldown_ms: int) -> bool:
        cooldown_key = (session_id, event_type)
        now = monotonic()
        next_ok = self._bonus_cooldowns.get(cooldown_key, 0.0)
        if now < next_ok:
            return False
        self._bonus_cooldowns[cooldown_key] = now + (cooldown_ms / 1000)
        return True

    def _enemy_count(self, context: dict[str, Any]) -> int:
        candidates = [context.get("enemy_count"), context.get("enemies_nearby"), context.get("enemy_wave")]
        for candidate in candidates:
            if candidate is None:
                continue
            try:
                return max(0, int(candidate))
            except (TypeError, ValueError):
                continue
        return 0

    def _tier_bonus_pulses(self, enemy_count: int, tiers: list[EnemyTier]) -> int:
        bonus = 0
        for tier in tiers:
            if enemy_count < tier.min_enemies:
                continue
            if tier.max_enemies is not None and enemy_count > tier.max_enemies:
                continue
            bonus = max(bonus, tier.extra_pulses)
        return bonus

    def _evaluate_hard_mode(self, session_id: str, mapping: EventMapping, context: dict[str, Any]) -> Decision:
        max_hp = int(context.get("max_hp", 0))
        current_hp = int(context.get("current_hp", 0))
        damage = int(context.get("damage", 0))
        enemy_count = self._enemy_count(context)

        if max_hp <= 0:
            return Decision(False, "hard_mode_missing_max_hp")

        state = self._hard_mode_states.get(session_id)
        if state is None:
            initial_missing_hp = damage if damage > 0 else max(0, max_hp - current_hp)
            if initial_missing_hp <= 0:
                return Decision(False, "hard_mode_not_started")
            self._hard_mode_states[session_id] = HardModeState(
                max_hp=max_hp,
                initial_missing_hp=initial_missing_hp,
                current_enemy_count=enemy_count,
            )
            return Decision(False, "hard_mode_started")

        state.current_enemy_count = enemy_count

        enemy_cfg = self.config.enemy_scaling
        dynamic_cooldown_ms = mapping.cooldown_ms
        if enemy_cfg.enabled:
            dynamic_cooldown_ms = max(
                enemy_cfg.min_tick_ms,
                mapping.cooldown_ms - (enemy_cfg.tick_reduction_per_enemy_ms * enemy_count),
            )

        if not self._consume_cooldown(session_id, "hard_mode", dynamic_cooldown_ms):
            return Decision(False, "cooldown_active")

        if current_hp >= state.max_hp:
            self._hard_mode_states.pop(session_id, None)
            return Decision(False, "hard_mode_completed")

        current_missing_hp = max(0, state.max_hp - current_hp)
        healed_hp = max(0, state.initial_missing_hp - current_missing_hp)
        if healed_hp <= 0:
            return Decision(False, "hard_mode_waiting_for_heal")

        ratio = healed_hp / state.max_hp
        configured_max = max(1, min(mapping.intensity, self.config.max_intensity))

        if enemy_cfg.enabled:
            enemy_factor = math.log1p(enemy_count) if enemy_cfg.use_logarithmic_intensity else enemy_count
            multiplier = 1 + (enemy_cfg.intensity_per_enemy * enemy_factor)
        else:
            multiplier = 1.0

        intensity = max(1, min(self.config.max_intensity, round(ratio * configured_max * multiplier)))

        duration_ms = mapping.duration_ms
        if enemy_cfg.enabled:
            duration_ms += enemy_cfg.duration_per_enemy_ms * enemy_count
            duration_cap = int(self.config.max_duration_ms * enemy_cfg.max_duration_multiplier)
        else:
            duration_cap = self.config.max_duration_ms

        duration_ms = max(100, min(duration_ms, duration_cap))
        duration_s = max(1, round(duration_ms / 1000))

        bonus_pulses = 0
        if enemy_cfg.enabled and enemy_count > 0:
            threshold_bonus = enemy_count // max(1, enemy_cfg.bonus_threshold)
            tier_bonus = self._tier_bonus_pulses(enemy_count, enemy_cfg.tiers)
            combat_bonus = 1 if (
                context.get("in_combat") and enemy_count >= enemy_cfg.combat_combo_min_enemies and enemy_cfg.combat_combo_enabled
            ) else 0

            if enemy_cfg.use_logarithmic_intensity:
                threshold_bonus = max(0, int(math.log(enemy_count + 1)))

            raw_bonus = threshold_bonus + tier_bonus + combat_bonus
            raw_bonus = max(0, min(raw_bonus, 6))

            if raw_bonus > 0 and self._consume_bonus_cooldown(session_id, "hard_mode_bonus", enemy_cfg.bonus_global_cooldown_ms):
                bonus_pulses = raw_bonus

        return Decision(
            True,
            "ok",
            op=MODE_TO_OP[mapping.mode],
            intensity=intensity,
            duration_s=duration_s,
            bonus_pulses=bonus_pulses,
            bonus_intensity_ratio=enemy_cfg.bonus_pulse_intensity_ratio,
            pulse_spacing_ms=enemy_cfg.pulse_spacing_ms,
        )
