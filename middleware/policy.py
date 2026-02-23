from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from middleware.config import AppConfig, EventMapping


MODE_TO_OP = {"shock": 0, "vibrate": 1, "beep": 2}


@dataclass
class Decision:
    allowed: bool
    reason: str
    op: int | None = None
    intensity: int | None = None
    duration_s: int | None = None


class PolicyEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self._cooldowns: dict[tuple[str, str], float] = {}

    def evaluate(self, session_id: str, event_type: str, armed: bool) -> Decision:
        mapping: EventMapping | None = self.config.event_mappings.get(event_type)
        if mapping is None:
            return Decision(False, "event_not_mapped")
        if not armed:
            return Decision(False, "session_not_armed")
        if mapping.mode == "shock" and not self.config.allow_shock:
            return Decision(False, "shock_disabled")

        cooldown_key = (session_id, event_type)
        now = monotonic()
        next_ok = self._cooldowns.get(cooldown_key, 0.0)
        if now < next_ok:
            return Decision(False, "cooldown_active")

        self._cooldowns[cooldown_key] = now + (mapping.cooldown_ms / 1000)

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
