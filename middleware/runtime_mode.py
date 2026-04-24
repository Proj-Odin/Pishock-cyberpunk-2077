from __future__ import annotations

import os
import logging
from enum import Enum
from typing import Callable


LIVE_CONFIRMATION_PHRASE = "I UNDERSTAND LIVE MODE"
RUNTIME_MODE_ENV = "PISHOCK_RUNTIME_MODE"
LIVE_CONFIRMATION_ENV = "PISHOCK_LIVE_CONFIRMATION"
logger = logging.getLogger(__name__)


class RuntimeMode(str, Enum):
    TEST = "test"
    BEEP = "beep"
    LIVE = "live"


def parse_runtime_mode(value: str | None) -> RuntimeMode | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    try:
        return RuntimeMode(normalized)
    except ValueError:
        return None


def runtime_mode_message(mode: RuntimeMode) -> str:
    if mode == RuntimeMode.TEST:
        return "[runtime] mode=test: dry-run only; no PiShock API calls will be made"
    if mode == RuntimeMode.BEEP:
        return "[runtime] mode=beep: only beep actions may reach PiShock"
    return "[runtime] mode=live: real device mode enabled"


def _live_confirmed_by_env() -> bool:
    return os.environ.get(LIVE_CONFIRMATION_ENV, "") == LIVE_CONFIRMATION_PHRASE


def _confirm_live(
    interactive: bool,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> bool:
    if _live_confirmed_by_env():
        logger.info("runtime mode live confirmation accepted source=environment")
        return True
    if not interactive:
        logger.warning("runtime mode live confirmation rejected source=non_interactive")
        output_func(
            f"[runtime] live mode requires {LIVE_CONFIRMATION_ENV}={LIVE_CONFIRMATION_PHRASE!r}; "
            "falling back to test"
        )
        return False
    try:
        typed = input_func(f"Type {LIVE_CONFIRMATION_PHRASE!r} to enable live mode: ")
    except (EOFError, OSError):
        logger.warning("runtime mode live confirmation unavailable source=prompt")
        output_func("[runtime] live mode confirmation unavailable; falling back to test")
        return False
    if typed == LIVE_CONFIRMATION_PHRASE:
        logger.info("runtime mode live confirmation accepted source=prompt")
        return True
    logger.warning("runtime mode live confirmation rejected source=prompt")
    output_func("[runtime] live mode confirmation did not match; falling back to test")
    return False


def choose_runtime_mode(
    cli_mode: str | None = None,
    interactive: bool = True,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> RuntimeMode:
    """Choose the runtime mode using CLI, env, prompt, then safe fallback.

    Invalid values fall back to test mode. Live mode is returned only after the
    exact confirmation phrase is typed or supplied through LIVE_CONFIRMATION_ENV.
    """

    if cli_mode is not None:
        mode = parse_runtime_mode(cli_mode)
        if mode is None:
            logger.warning("runtime mode invalid source=cli selected=test")
            output_func(f"[runtime] invalid CLI mode {cli_mode!r}; falling back to test")
            return RuntimeMode.TEST
        if mode == RuntimeMode.LIVE and not _confirm_live(interactive, input_func, output_func):
            logger.info("runtime mode selected mode=test source=cli_live_confirmation_fallback")
            return RuntimeMode.TEST
        logger.info("runtime mode selected mode=%s source=cli", mode.value)
        return mode

    env_value = os.environ.get(RUNTIME_MODE_ENV)
    if env_value is not None:
        mode = parse_runtime_mode(env_value)
        if mode is None:
            logger.warning("runtime mode invalid source=environment selected=test")
            output_func(f"[runtime] invalid {RUNTIME_MODE_ENV}={env_value!r}; falling back to test")
            return RuntimeMode.TEST
        if mode == RuntimeMode.LIVE and not _confirm_live(interactive, input_func, output_func):
            logger.info("runtime mode selected mode=test source=environment_live_confirmation_fallback")
            return RuntimeMode.TEST
        logger.info("runtime mode selected mode=%s source=environment", mode.value)
        return mode

    if interactive:
        output_func("Choose runtime mode:")
        output_func("1. test  - dry-run/mock only; no PiShock API/device calls")
        output_func("2. beep  - real PiShock API/device allowed for beep only; vibrate and shock blocked")
        output_func("3. live  - real configured behavior allowed; requires explicit confirmation")
        try:
            selected = input_func("Runtime mode [test]: ")
        except (EOFError, OSError):
            logger.info("runtime mode selected mode=test source=prompt_unavailable")
            return RuntimeMode.TEST
        mode = parse_runtime_mode(selected)
        if selected.strip() == "1":
            mode = RuntimeMode.TEST
        elif selected.strip() == "2":
            mode = RuntimeMode.BEEP
        elif selected.strip() == "3":
            mode = RuntimeMode.LIVE
        if mode is None:
            logger.info("runtime mode selected mode=test source=prompt_default")
            return RuntimeMode.TEST
        if mode == RuntimeMode.LIVE and not _confirm_live(True, input_func, output_func):
            logger.info("runtime mode selected mode=test source=prompt_live_confirmation_fallback")
            return RuntimeMode.TEST
        logger.info("runtime mode selected mode=%s source=prompt", mode.value)
        return mode

    logger.info("runtime mode selected mode=test source=fallback")
    return RuntimeMode.TEST


def log_runtime_mode(mode: RuntimeMode, output_func: Callable[[str], None] = print) -> None:
    message = runtime_mode_message(mode)
    logger.info(message)
    if mode == RuntimeMode.TEST:
        logger.info("test mode dry-run active")
    elif mode == RuntimeMode.BEEP:
        logger.info("beep mode restrictions active")
    output_func(message)
