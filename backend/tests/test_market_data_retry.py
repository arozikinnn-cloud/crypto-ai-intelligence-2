import httpx
import pytest

from app.services.market_data.http import get_json_with_retry


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    async def get(self, _path, params=None):
        self.calls += 1
        response = next(self.responses)
        response.request = httpx.Request("GET", "https://example.test/data")
        return response


@pytest.mark.asyncio
async def test_transient_server_error_is_retried(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("app.services.market_data.http.asyncio.sleep", no_sleep)
    client = FakeClient([
        httpx.Response(503, json={"error": "temporary"}),
        httpx.Response(200, json={"ok": True}),
    ])
    result = await get_json_with_retry(client, "/data", {}, "test source")
    assert result == {"ok": True}
    assert client.calls == 2


@pytest.mark.asyncio
async def test_permanent_http_error_is_not_retried(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("app.services.market_data.http.asyncio.sleep", no_sleep)
    client = FakeClient([httpx.Response(400, json={"error": "bad request"})])
    with pytest.raises(Exception, match="HTTP 400"):
        await get_json_with_retry(client, "/data", {}, "test source")
    assert client.calls == 1
