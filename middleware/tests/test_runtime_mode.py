from middleware.runtime_mode import (
    LIVE_CONFIRMATION_ENV,
    LIVE_CONFIRMATION_PHRASE,
    RUNTIME_MODE_ENV,
    RuntimeMode,
    choose_runtime_mode,
)


def test_default_runtime_mode_is_test(monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_MODE_ENV, raising=False)
    monkeypatch.delenv(LIVE_CONFIRMATION_ENV, raising=False)

    assert choose_runtime_mode(interactive=False) == RuntimeMode.TEST


def test_enter_selects_test(monkeypatch) -> None:
    monkeypatch.delenv(RUNTIME_MODE_ENV, raising=False)

    mode = choose_runtime_mode(interactive=True, input_func=lambda _: "", output_func=lambda _: None)

    assert mode == RuntimeMode.TEST


def test_env_selects_test(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_MODE_ENV, "test")

    assert choose_runtime_mode(interactive=False) == RuntimeMode.TEST


def test_env_selects_beep(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_MODE_ENV, "beep")

    assert choose_runtime_mode(interactive=False) == RuntimeMode.BEEP


def test_env_live_requires_confirmation(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_MODE_ENV, "live")
    monkeypatch.delenv(LIVE_CONFIRMATION_ENV, raising=False)

    assert choose_runtime_mode(interactive=False, output_func=lambda _: None) == RuntimeMode.TEST


def test_env_live_with_confirmation_selects_live(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_MODE_ENV, "live")
    monkeypatch.setenv(LIVE_CONFIRMATION_ENV, LIVE_CONFIRMATION_PHRASE)

    assert choose_runtime_mode(interactive=False) == RuntimeMode.LIVE


def test_interactive_live_confirmation_selects_live(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_MODE_ENV, "live")
    monkeypatch.delenv(LIVE_CONFIRMATION_ENV, raising=False)

    assert (
        choose_runtime_mode(
            interactive=True,
            input_func=lambda _: LIVE_CONFIRMATION_PHRASE,
            output_func=lambda _: None,
        )
        == RuntimeMode.LIVE
    )


def test_invalid_env_falls_back_to_test(monkeypatch) -> None:
    monkeypatch.setenv(RUNTIME_MODE_ENV, "banana")

    assert choose_runtime_mode(interactive=False, output_func=lambda _: None) == RuntimeMode.TEST
