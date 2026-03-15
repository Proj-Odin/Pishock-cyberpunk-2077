from __future__ import annotations

import asyncio
import logging
from typing import Any


logger = logging.getLogger(__name__)


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
                result = self._call_shocker_method(shocker, "shock", duration_s, intensity)
            elif op == 1:
                result = self._call_shocker_method(shocker, "vibrate", duration_s, intensity)
            elif op == 2:
                result = self._call_shocker_method(shocker, "beep", duration_s, intensity)
            else:
                raise RuntimeError("invalid_operation")
        except Exception:
            logger.exception("pishock operation failed")
            raise

        return 200, str(result)
