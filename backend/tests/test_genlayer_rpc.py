import httpx
import pytest

from backend.genlayer_client import GenLayerClientWrapper


def rpc_client(transport: httpx.AsyncBaseTransport, attempts: int = 3):
    client = object.__new__(GenLayerClientWrapper)
    client.rpc_url = "https://rpc.test"
    client.rpc_timeout_sec = 1.0
    client.rpc_max_attempts = attempts
    client.rpc_retry_backoff_sec = 0.0
    client._http_client = httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(1.0),
    )
    return client


@pytest.mark.asyncio
async def test_rpc_call_retries_transient_transport_failures():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": "0x1"})

    client = rpc_client(httpx.MockTransport(handler))
    try:
        result = await client._rpc_call("eth_chainId", [])
    finally:
        await client.close()

    assert result == "0x1"
    assert attempts == 3


@pytest.mark.asyncio
async def test_rpc_call_does_not_retry_protocol_errors():
    attempts = 0

    def handler(_request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "invalid params"}},
        )

    client = rpc_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(RuntimeError, match="invalid params"):
            await client._rpc_call("eth_call", [])
    finally:
        await client.close()

    assert attempts == 1
