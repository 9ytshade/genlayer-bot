import asyncio

import pytest

from backend.logs_store import MemoryLogsStore


WALLET_A = "0x1111111111111111111111111111111111111111"
WALLET_B = "0x2222222222222222222222222222222222222222"


@pytest.mark.asyncio
async def test_activity_logs_are_wallet_scoped_and_redacted():
    store = MemoryLogsStore(max_items=50)
    await store.append(
        "INFO",
        "TRANSACTION_READY",
        "Transaction prepared.",
        {
            "network": "bradbury",
            "status": "PREPARED",
            "wallet_address": WALLET_A,
            "txHash": "0x" + "ab" * 32,
            "prompt": "send everything",
            "source": "class Contract: pass",
            "error": "provider URL https://rpc.example",
            "errors": ["first", "second"],
            "method": "read https://private.example/0x1111111111111111111111111111111111111111",
        },
        wallet_address=WALLET_A,
    )
    await store.append(
        "INFO",
        "OTHER_WALLET_EVENT",
        "Other wallet event.",
        {"network": "studionet"},
        wallet_address=WALLET_B,
    )

    wallet_a_items = await store.recent(WALLET_A)
    wallet_b_items = await store.recent(WALLET_B)

    assert [item["event"] for item in wallet_a_items] == ["TRANSACTION_READY"]
    assert [item["event"] for item in wallet_b_items] == ["OTHER_WALLET_EVENT"]
    assert wallet_a_items[0]["meta"] == {
        "network": "bradbury",
        "status": "PREPARED",
        "errorCount": 2,
        "method": "read [redacted]",
    }


@pytest.mark.asyncio
async def test_activity_stream_only_receives_matching_wallet_events():
    store = MemoryLogsStore(max_items=50)
    queue = await store.subscribe(WALLET_A)
    try:
        await store.append("INFO", "OTHER", "Other.", wallet_address=WALLET_B)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.01)

        await store.append("SUCCESS", "MATCH", "Matching.", wallet_address=WALLET_A)
        item = await asyncio.wait_for(queue.get(), timeout=0.1)
        assert item["event"] == "MATCH"
    finally:
        await store.unsubscribe(queue)
