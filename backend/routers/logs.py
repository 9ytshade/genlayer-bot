from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio

from ..logs_store import logs_store

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def get_recent_logs(limit: int = Query(default=80, ge=1, le=300)):
    items = await logs_store.recent(limit=limit)
    return {"items": items}


@router.websocket("/stream")
async def logs_stream(websocket: WebSocket):
    await websocket.accept()
    queue = await logs_store.subscribe()
    try:
        # Send a small backlog so users immediately see context.
        backlog = await logs_store.recent(limit=30)
        await websocket.send_json({"type": "backlog", "items": backlog})

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=2.0)
                await websocket.send_json({"type": "log", "item": item})
            except asyncio.TimeoutError:
                # Keep loop responsive so server shutdown/cancellation is not blocked.
                continue
    except WebSocketDisconnect:
        pass
    finally:
        await logs_store.unsubscribe(queue)
