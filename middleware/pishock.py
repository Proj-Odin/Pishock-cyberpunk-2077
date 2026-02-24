from __future__ import annotations

import asyncio
from typing import Any


class PiShockClient:
    """Thin wrapper around python-pishock to keep middleware logic simple."""

    def __init__(self, config: dict[str, Any]):
        self.username = str(config.get("username", "")).strip()
        self.api_key = str(config.get("api_key", "")).strip()
        self.share_code = str(config.get("share_code", "")).strip()
        self.name = str(config.get("name", "CyberpunkBridge")).strip()
        self.dry_run = bool(config.get("dry_run", False))

        if not self.username or not self.api_key or not self.share_code:
            raise RuntimeError("pishock_credentials_missing")

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        return await asyncio.to_thread(self._operate_sync, op, intensity, duration_s)

    def _build_shocker(self):
        # Preferred path for current `pishock` package
        try:
            from pishock import PiShockAPI

            api = PiShockAPI(self.username, self.api_key)
            return api.shocker(self.share_code)
        except Exception as exc:
            # Fallback to legacy constructor variants (older wrappers / repo assumptions)
            try:
                from pishock import Shocker
            except Exception as exc2:
                raise RuntimeError("python_pishock_not_installed") from exc2

            for kwargs in (
                {
                    "username": self.username,
                    "api_key": self.api_key,
                    "share_code": self.share_code,
                    "name": self.name,
                },
                {
                    "username": self.username,
                    "api_key": self.api_key,
                    "code": self.share_code,
                    "name": self.name,
                },
                {
                    "username": self.username,
                    "api_key": self.api_key,
                    "share_code": self.share_code,
                },
                {
                    "username": self.username,
                    "api_key": self.api_key,
                    "code": self.share_code,
                },
            ):
                try:
                    return Shocker(**kwargs)
                except TypeError:
                    continue

            raise RuntimeError("python_pishock_shocker_init_failed") from exc

    def _operate_sync(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        try:
            if self.dry_run:
                return 200, f"dry_run op={op} intensity={intensity} duration_s={duration_s}"

            shocker = self._build_shocker()

            if op == 0:
                result = shocker.shock(duration=duration_s, intensity=intensity)
            elif op == 1:
                result = shocker.vibrate(duration=duration_s, intensity=intensity)
            elif op == 2:
                result = shocker.beep(duration=duration_s, intensity=intensity)
            else:
                raise RuntimeError("invalid_operation")

            return 200, str(result)
        except Exception as exc:
            print(f"[pishock_client] operate failed: {type(exc).__name__}: {exc}")
            raise
