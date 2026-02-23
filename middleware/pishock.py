from __future__ import annotations

from typing import Any



class PiShockClient:
    """PiShock client using the newer discovery/auth APIs to resolve target shocker details.

    Note:
    - Discovery/auth uses auth.pishock.com + ps.pishock.com endpoints.
    - Actuation remains HTTP operate payload based on resolved share code for compatibility.
    """

    def __init__(self, config: dict[str, Any]):
        self.username = config.get("username", "")
        self.api_key = config.get("api_key", "")
        self.user_id = config.get("user_id")
        self.share_id = config.get("share_id")
        self.share_code = config.get("share_code", "")
        self.target_shocker_name = config.get("target_shocker_name", "")
        self.name = config.get("name", "CyberpunkBridge")

        self.auth_base = config.get("auth_base", "https://auth.pishock.com")
        self.ps_base = config.get("ps_base", "https://ps.pishock.com")
        self.operate_endpoint = config.get("operate_endpoint", "https://do.pishock.com/api/apioperate")

    async def _ensure_resolved(self) -> None:
        if self.share_code:
            return

        if not self.username or not self.api_key:
            raise RuntimeError("pishock_credentials_missing")

        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            if not self.user_id:
                auth_resp = await client.get(
                    f"{self.auth_base}/Auth/GetUserIfAPIKeyValid",
                    params={"apikey": self.api_key, "username": self.username},
                )
                auth_resp.raise_for_status()
                auth_json = auth_resp.json()
                self.user_id = auth_json.get("UserID") or auth_json.get("userID") or auth_json.get("userid")
                if not self.user_id:
                    raise RuntimeError("pishock_userid_resolution_failed")

            # Resolve share IDs owned by current account.
            share_resp = await client.get(
                f"{self.ps_base}/PiShock/GetShareCodesByOwner",
                params={"UserId": self.user_id, "Token": self.api_key, "api": "true"},
            )
            share_resp.raise_for_status()
            share_data = share_resp.json()

            share_ids: list[int] = []
            for ids in share_data.values() if isinstance(share_data, dict) else []:
                if isinstance(ids, list):
                    for value in ids:
                        try:
                            share_ids.append(int(value))
                        except (TypeError, ValueError):
                            continue

            if self.share_id:
                share_ids = [int(self.share_id)]

            if not share_ids:
                raise RuntimeError("pishock_no_share_ids_found")

            params: list[tuple[str, str]] = [
                ("UserId", str(self.user_id)),
                ("Token", self.api_key),
                ("api", "true"),
            ]
            for sid in share_ids:
                params.append(("shareIds", str(sid)))

            shockers_resp = await client.get(f"{self.ps_base}/PiShock/GetShockersByShareIds", params=params)
            shockers_resp.raise_for_status()
            shockers_data = shockers_resp.json()

            candidates: list[dict[str, Any]] = []
            if isinstance(shockers_data, dict):
                for items in shockers_data.values():
                    if isinstance(items, list):
                        candidates.extend(item for item in items if isinstance(item, dict))

            if not candidates:
                raise RuntimeError("pishock_no_shockers_found")

            selected = candidates[0]
            if self.target_shocker_name:
                for candidate in candidates:
                    if str(candidate.get("shockerName", "")).lower() == self.target_shocker_name.lower():
                        selected = candidate
                        break

            resolved_share_code = selected.get("shareCode")
            if not resolved_share_code:
                raise RuntimeError("pishock_share_code_not_available")

            self.share_code = str(resolved_share_code)

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        await self._ensure_resolved()

        payload = {
            "Username": self.username,
            "Apikey": self.api_key,
            "Code": self.share_code,
            "Name": self.name,
            "Op": op,
            "Intensity": intensity,
            "Duration": duration_s,
        }
        import httpx

        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(self.operate_endpoint, json=payload)
        return response.status_code, response.text
