import asyncio
import sys
import types

from middleware.pishock import PiShockClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.text = "ok"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, params=None):
        if "GetUserIfAPIKeyValid" in url:
            return FakeResponse({"UserID": 321})
        if "GetShareCodesByOwner" in url:
            return FakeResponse({"owner": [111]})
        if "GetShockersByShareIds" in url:
            return FakeResponse({"owner": [{"shockerName": "alpha", "shareCode": "SCODE"}]})
        raise AssertionError(f"Unexpected URL {url}")

    async def post(self, url, json=None):
        assert json["Code"] == "SCODE"
        return FakeResponse({"ok": True})


def test_pishock_client_resolves_share_code(monkeypatch):
    fake_httpx = types.SimpleNamespace(AsyncClient=FakeAsyncClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)

    client = PiShockClient({"username": "u", "api_key": "k", "name": "n"})

    status, _ = asyncio.run(client.operate(op=1, intensity=10, duration_s=1))
    assert status == 200
    assert client.user_id == 321
    assert client.share_code == "SCODE"
