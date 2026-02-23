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
            "player_damaged": EventMapping(mode="shock", intensity=50, duration_ms=2500, cooldown_ms=500),
            "player_hard_mode_tick": EventMapping(mode="hard", intensity=20, duration_ms=500, cooldown_ms=0),
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


def test_hard_mode_ramps_with_healing() -> None:
    engine = PolicyEngine(build_config(allow_shock=True))

    start = engine.evaluate(
        "session-hard",
        "player_hard_mode_tick",
        armed=True,
        context={"max_hp": 400, "current_hp": 100, "damage": 300},
    )
    assert not start.allowed
    assert start.reason == "hard_mode_started"

    second_1 = engine.evaluate(
        "session-hard",
        "player_hard_mode_tick",
        armed=True,
        context={"max_hp": 400, "current_hp": 200},
    )
    assert second_1.allowed
    assert second_1.intensity == 5

    second_2 = engine.evaluate(
        "session-hard",
        "player_hard_mode_tick",
        armed=True,
        context={"max_hp": 400, "current_hp": 300},
    )
    assert second_2.allowed
    assert second_2.intensity == 10

    second_3 = engine.evaluate(
        "session-hard",
        "player_hard_mode_tick",
        armed=True,
        context={"max_hp": 400, "current_hp": 400},
    )
    assert not second_3.allowed
    assert second_3.reason == "hard_mode_completed"
