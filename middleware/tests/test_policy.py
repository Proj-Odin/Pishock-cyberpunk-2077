from middleware.config import AppConfig, EventMapping
from middleware.policy import PolicyEngine


def build_config(allow_shock: bool = False) -> AppConfig:
    return AppConfig(
        hmac_secret="secret",
        allow_shock=allow_shock,
        max_intensity=20,
        max_duration_ms=1500,
        default_cooldown_ms=1000,
        pishock={},
        event_mappings={
            "player_damaged": EventMapping(mode="shock", intensity=50, duration_ms=2500, cooldown_ms=500)
        },
    )


def test_shock_disabled() -> None:
    engine = PolicyEngine(build_config(allow_shock=False))
    decision = engine.evaluate("s1", "player_damaged", armed=True)
    assert not decision.allowed
    assert decision.reason == "shock_disabled"


def test_caps_and_cooldown() -> None:
    engine = PolicyEngine(build_config(allow_shock=True))
    first = engine.evaluate("s1", "player_damaged", armed=True)
    assert first.allowed
    assert first.intensity == 20
    assert first.duration_s == 2
    second = engine.evaluate("s1", "player_damaged", armed=True)
    assert not second.allowed
    assert second.reason == "cooldown_active"
