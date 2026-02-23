from __future__ import annotations

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
