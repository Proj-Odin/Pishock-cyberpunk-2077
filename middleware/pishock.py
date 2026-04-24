from __future__ import annotations

import asyncio
import logging
from typing import Any

from middleware.runtime_mode import RuntimeMode, log_runtime_mode


logger = logging.getLogger(__name__)
OP_SHOCK = 0
OP_VIBRATE = 1
OP_BEEP = 2
OP_NAMES = {OP_SHOCK: "shock", OP_VIBRATE: "vibrate", OP_BEEP: "beep"}


class RuntimeModeOperationBlocked(RuntimeError):
    pass


def _config_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return default


class DryRunPiShockClient:
    """Safe PiShock stand-in used by default and by tests."""

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        logger.info(
            "dry-run operation op=%s intensity=%s duration_s=%s no_real_api=true",
            OP_NAMES.get(op, f"unknown:{op}"),
            intensity,
            duration_s,
        )
        return 200, f"dry_run op={op} intensity={intensity} duration_s={duration_s}"


class BeepOnlyPiShockClient:
    """PiShock wrapper that allows only beep operations through."""

    def __init__(self, real_client: Any):
        self.real_client = real_client

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        if op != OP_BEEP:
            logger.warning(
                "runtime mode block mode=beep op=%s reason=runtime_mode_beep_blocks_non_beep_operation",
                OP_NAMES.get(op, f"unknown:{op}"),
            )
            raise RuntimeModeOperationBlocked("runtime_mode_beep_blocks_non_beep_operation")
        logger.info("beep mode operation allowed op=beep intensity=%s duration_s=%s", intensity, duration_s)
        return await self.real_client.operate(op, intensity, duration_s)


def _coerce_runtime_mode(mode: RuntimeMode | str | None) -> RuntimeMode:
    if isinstance(mode, RuntimeMode):
        return mode
    if isinstance(mode, str):
        try:
            return RuntimeMode(mode.strip().lower())
        except ValueError:
            return RuntimeMode.TEST
    return RuntimeMode.TEST


def build_pishock_client(config: dict[str, Any], mode: RuntimeMode | str | None = None):
    runtime_mode = _coerce_runtime_mode(mode)
    log_runtime_mode(runtime_mode)

    if runtime_mode == RuntimeMode.TEST or _config_bool(config.get("dry_run", True), default=True):
        logger.info("pishock client mode=dry_run runtime_mode=%s", runtime_mode.value)
        return DryRunPiShockClient()

    real_client = PiShockClient(config)
    if runtime_mode == RuntimeMode.BEEP:
        logger.info("pishock client mode=beep_only")
        return BeepOnlyPiShockClient(real_client)
    logger.info("pishock client mode=live")
    return real_client


class PiShockClient:
    """Thin wrapper around python-pishock to keep middleware logic simple."""

    def __init__(self, config: dict[str, Any]):
        self.username = str(config.get("username", "")).strip()
        self.api_key = str(config.get("api_key", "")).strip()
        self.share_code = str(config.get("share_code", "")).strip()
        self.name = str(config.get("name", "CyberpunkBridge")).strip()

        if not self.username or not self.api_key or not self.share_code:
            raise RuntimeError("pishock_credentials_missing")

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        return await asyncio.to_thread(self._operate_sync, op, intensity, duration_s)

    def _build_shocker(self):
        try:
            from pishock import PiShockAPI
        except Exception:
            PiShockAPI = None

        if PiShockAPI is not None:
            for api_args, api_kwargs in (
                ((self.username, self.api_key), {}),
                ((), {"username": self.username, "api_key": self.api_key}),
            ):
                try:
                    api = PiShockAPI(*api_args, **api_kwargs)
                    for args, kwargs in (
                        ((self.share_code, self.name), {}),
                        ((self.share_code,), {"name": self.name}),
                        ((), {"share_code": self.share_code, "name": self.name}),
                        ((), {"code": self.share_code, "name": self.name}),
                    ):
                        try:
                            return api.shocker(*args, **kwargs)
                        except TypeError:
                            continue
                except TypeError:
                    continue

        try:
            from pishock import Shocker
        except Exception as exc:  # pragma: no cover - depends on runtime install
            raise RuntimeError("python_pishock_not_installed") from exc

        # Support common constructor variants across python-pishock versions.
        for kwargs in (
            {"username": self.username, "api_key": self.api_key, "share_code": self.share_code, "name": self.name},
            {"username": self.username, "api_key": self.api_key, "code": self.share_code, "name": self.name},
            {"username": self.username, "api_key": self.api_key, "share_code": self.share_code},
            {"username": self.username, "api_key": self.api_key, "code": self.share_code},
        ):
            try:
                return Shocker(**kwargs)
            except TypeError:
                continue

        raise RuntimeError("python_pishock_shocker_init_failed")

    @staticmethod
    def _call_shocker_method(shocker: Any, method_name: str, duration_s: int, intensity: int) -> Any:
        method = getattr(shocker, method_name)

        if method_name == "beep":
            try:
                return method(duration=duration_s)
            except TypeError:
                return method(duration=duration_s, intensity=intensity)

        for args, kwargs in (
            ((), {"duration": duration_s, "intensity": intensity}),
            ((duration_s, intensity), {}),
        ):
            try:
                return method(*args, **kwargs)
            except TypeError:
                continue

        raise RuntimeError(f"python_pishock_{method_name}_call_failed")

    def _operate_sync(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        try:
            shocker = self._build_shocker()

            if op == 0:
                logger.info("pishock operation dispatch op=shock intensity=%s duration_s=%s", intensity, duration_s)
                result = self._call_shocker_method(shocker, "shock", duration_s, intensity)
            elif op == 1:
                logger.info("pishock operation dispatch op=vibrate intensity=%s duration_s=%s", intensity, duration_s)
                result = self._call_shocker_method(shocker, "vibrate", duration_s, intensity)
            elif op == 2:
                logger.info("pishock operation dispatch op=beep intensity=%s duration_s=%s", intensity, duration_s)
                result = self._call_shocker_method(shocker, "beep", duration_s, intensity)
            else:
                raise RuntimeError("invalid_operation")
        except Exception as exc:
            logger.error("pishock operation failed error_type=%s", type(exc).__name__)
            raise

        return 200, str(result)
