from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_LEVEL_ENV = "PISHOCK_LOG_LEVEL"
DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "middleware.log"
SENSITIVE_KEYS = (
    "api_key",
    "username",
    "share_code",
    "hmac_secret",
    "secret",
    "token",
    "authorization",
    "x-signature",
)


def log_path_from_env() -> Path:
    return Path(os.environ.get("PISHOCK_LOG_FILE", DEFAULT_LOG_PATH)).expanduser()


def _level_from_env(default: str = "INFO") -> int:
    raw_level = os.environ.get(LOG_LEVEL_ENV, default).strip().upper()
    return getattr(logging, raw_level, logging.INFO)


def redact_text(value: object) -> str:
    text = str(value)
    for key in SENSITIVE_KEYS:
        text = re.sub(
            rf"(?i)((?:['\"]?){re.escape(key)}(?:['\"]?)\s*[:=]\s*['\"])([^'\"]+)(['\"])",
            rf"\1[REDACTED]\3",
            text,
        )
        text = re.sub(
            rf"(?i)(\b{re.escape(key)}\b\s*[:=]\s*)(['\"]?)([^,'\"\s}}\]\[]+)(['\"]?)",
            rf"\1\2[REDACTED]\4",
            text,
        )
    text = re.sub(r"(?i)(\bauthorization\b\s*[:=]\s*)([^,\r\n]+)", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(\bx-signature\b\s*[:=]\s*)([^,\r\n\s]+)", r"\1[REDACTED]", text)
    return text


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def configure_logging(
    log_path: Path | str | None = None,
    level: int | str | None = None,
    force: bool = False,
) -> Path:
    resolved_path = Path(log_path).expanduser() if log_path is not None else log_path_from_env()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(level, str):
        resolved_level = getattr(logging, level.strip().upper(), logging.INFO)
    elif isinstance(level, int):
        resolved_level = level
    else:
        resolved_level = _level_from_env()

    logger = logging.getLogger("middleware")
    if force:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
    elif any(getattr(handler, "_pishock_handler", False) for handler in logger.handlers):
        logger.setLevel(resolved_level)
        return resolved_path

    logger.setLevel(resolved_level)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    redaction_filter = RedactionFilter()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(resolved_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(redaction_filter)
    console_handler._pishock_handler = True

    file_handler = RotatingFileHandler(
        resolved_path,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction_filter)
    file_handler._pishock_handler = True

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.info("logging initialized log_file=%s level=%s", resolved_path, logging.getLevelName(resolved_level))
    return resolved_path
