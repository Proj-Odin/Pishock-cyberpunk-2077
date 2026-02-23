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

        if not self.username or not self.api_key or not self.share_code:
            raise RuntimeError("pishock_credentials_missing")

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        return await asyncio.to_thread(self._operate_sync, op, intensity, duration_s)

    def _build_shocker(self):
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

    def _operate_sync(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
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
import httpx


class PiShockClient:
    def __init__(self, config: dict):
        self.endpoint = config.get("endpoint", "https://do.pishock.com/api/apioperate")
        self.username = config.get("username", "")
        self.api_key = config.get("api_key", "")
        self.share_code = config.get("share_code", "")
        self.name = config.get("name", "CyberpunkBridge")

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        payload = {
            "Username": self.username,
            "Apikey": self.api_key,
            "Code": self.share_code,
            "Name": self.name,
            "Op": op,
            "Intensity": intensity,
            "Duration": duration_s,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(self.endpoint, json=payload)
        return response.status_code, response.text
