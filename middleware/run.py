from __future__ import annotations

import argparse
import logging
import os

import uvicorn

from middleware.logging_config import configure_logging
from middleware.runtime_mode import (
    LIVE_CONFIRMATION_ENV,
    LIVE_CONFIRMATION_PHRASE,
    RUNTIME_MODE_ENV,
    RuntimeMode,
    choose_runtime_mode,
    log_runtime_mode,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cyberpunk -> PiShock middleware")
    parser.add_argument("--mode", choices=[mode.value for mode in RuntimeMode], help="Runtime mode: test, beep, or live")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", dest="reload", action="store_true", default=False)
    parser.add_argument("--no-reload", dest="reload", action="store_false")
    args = parser.parse_args()

    log_path = configure_logging()
    logger = logging.getLogger(__name__)
    print(f"[runtime] logs: {log_path}")
    logger.info("launcher starting host=%s port=%s reload=%s log_file=%s", args.host, args.port, args.reload, log_path)

    mode = choose_runtime_mode(cli_mode=args.mode, interactive=True)
    os.environ[RUNTIME_MODE_ENV] = mode.value
    if mode == RuntimeMode.LIVE:
        # The uvicorn reload worker is non-interactive; carry forward the already typed confirmation.
        os.environ[LIVE_CONFIRMATION_ENV] = LIVE_CONFIRMATION_PHRASE
    elif LIVE_CONFIRMATION_ENV in os.environ:
        os.environ.pop(LIVE_CONFIRMATION_ENV)

    log_runtime_mode(mode)
    logger.info("uvicorn starting host=%s port=%s reload=%s runtime_mode=%s", args.host, args.port, args.reload, mode.value)
    uvicorn.run("middleware.app:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
