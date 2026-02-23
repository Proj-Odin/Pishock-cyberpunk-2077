from middleware.config import AppConfig, EnemyScalingConfig, EnemyTier, EventMapping
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
            "player_hard_mode_tick": EventMapping(mode="hard", intensity=20, duration_ms=500, cooldown_ms=500),
        },
        enemy_scaling=EnemyScalingConfig(
            enabled=True,
            intensity_per_enemy=0.1,
            use_logarithmic_intensity=False,
            bonus_threshold=3,
            bonus_pulse_intensity_ratio=0.5,
            bonus_global_cooldown_ms=0,
            min_tick_ms=250,
            tick_reduction_per_enemy_ms=100,
            duration_per_enemy_ms=100,
            max_duration_multiplier=2.0,
            combat_combo_enabled=True,
            combat_combo_min_enemies=2,
            pulse_spacing_ms=120,
            tiers=[
                EnemyTier(min_enemies=1, max_enemies=2, extra_pulses=0),
                EnemyTier(min_enemies=3, max_enemies=5, extra_pulses=1),
                EnemyTier(min_enemies=6, max_enemies=None, extra_pulses=2),
            ],
        ),
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
        context={"max_hp": 400, "current_hp": 200, "enemy_count": 0},
    )
    assert second_1.allowed
    assert second_1.intensity == 5


def test_enemy_scaling_bonus_and_duration() -> None:
    engine = PolicyEngine(build_config(allow_shock=True))
    engine.evaluate("session-hard", "player_hard_mode_tick", armed=True, context={"max_hp": 400, "current_hp": 100, "damage": 300})

    decision = engine.evaluate(
        "session-hard",
        "player_hard_mode_tick",
        armed=True,
        context={"max_hp": 400, "current_hp": 200, "enemy_count": 6, "in_combat": True},
    )
    assert decision.allowed
    assert decision.intensity == 8  # 5 * (1 + 0.1*6)
    assert decision.duration_s == 1
    assert decision.bonus_pulses >= 5


def test_hard_mode_completion() -> None:
    engine = PolicyEngine(build_config(allow_shock=True))
    engine.evaluate("session-hard", "player_hard_mode_tick", armed=True, context={"max_hp": 400, "current_hp": 100, "damage": 300})
    done = engine.evaluate("session-hard", "player_hard_mode_tick", armed=True, context={"max_hp": 400, "current_hp": 400})
    assert not done.allowed
    assert done.reason == "hard_mode_completed"
