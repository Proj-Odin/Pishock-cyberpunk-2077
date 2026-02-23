from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

from middleware.config import AppConfig, EventMapping


MODE_TO_OP = {"shock": 0, "vibrate": 1, "beep": 2, "hard": 0}


@dataclass
class Decision:
    allowed: bool
    reason: str
    op: int | None = None
    intensity: int | None = None
    duration_s: int | None = None


@dataclass
class HardModeState:
    max_hp: int
    initial_missing_hp: int


class PolicyEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self._cooldowns: dict[tuple[str, str], float] = {}
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

        return Decision(
            True,
            "ok",
            op=MODE_TO_OP[mapping.mode],
            intensity=intensity,
            duration_s=duration_s,
        )

    def _consume_cooldown(self, session_id: str, event_type: str, cooldown_ms: int) -> bool:
        cooldown_key = (session_id, event_type)
        now = monotonic()
        next_ok = self._cooldowns.get(cooldown_key, 0.0)
        if now < next_ok:
            return False
        self._cooldowns[cooldown_key] = now + (cooldown_ms / 1000)
        return True

    def _evaluate_hard_mode(self, session_id: str, mapping: EventMapping, context: dict[str, Any]) -> Decision:
        max_hp = int(context.get("max_hp", 0))
        current_hp = int(context.get("current_hp", 0))
        damage = int(context.get("damage", 0))

        if max_hp <= 0:
            return Decision(False, "hard_mode_missing_max_hp")

        state = self._hard_mode_states.get(session_id)
        if state is None:
            initial_missing_hp = damage if damage > 0 else max(0, max_hp - current_hp)
            if initial_missing_hp <= 0:
                return Decision(False, "hard_mode_not_started")
            self._hard_mode_states[session_id] = HardModeState(max_hp=max_hp, initial_missing_hp=initial_missing_hp)
            return Decision(False, "hard_mode_started")

        if not self._consume_cooldown(session_id, "hard_mode", mapping.cooldown_ms):
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
        intensity = max(1, round(ratio * configured_max))
        duration_ms = max(100, min(mapping.duration_ms, self.config.max_duration_ms))
        duration_s = max(1, round(duration_ms / 1000))

        return Decision(True, "ok", op=MODE_TO_OP[mapping.mode], intensity=intensity, duration_s=duration_s)
