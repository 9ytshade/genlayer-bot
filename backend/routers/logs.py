from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
import asyncio

from ..auth import decode_access_token, get_current_user, normalize_address
from ..database import SessionLocal
from ..logs_store import logs_store
from ..models import User

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def get_recent_logs(
    limit: int = Query(default=80, ge=1, le=300),
    current_user: User = Depends(get_current_user),
):
    items = await logs_store.recent(
        wallet_address=current_user.connected_wallet_address,
        limit=limit,
    )
    return {"items": items}


@router.websocket("/stream")
async def logs_stream(websocket: WebSocket):
    requested_protocols = [
        protocol.strip()
        for protocol in websocket.headers.get("sec-websocket-protocol", "").split(",")
        if protocol.strip()
    ]
    if len(requested_protocols) != 2 or requested_protocols[0] != "genlayer-auth":
        await websocket.close(code=4401)
        return

    try:
        payload = decode_access_token(requested_protocols[1])
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError("Missing wallet subject")
        wallet_address = normalize_address(subject)
        db = SessionLocal()
        try:
            if not db.query(User).filter(User.connected_wallet_address == wallet_address).first():
                raise ValueError("Authenticated user was not found")
        finally:
            db.close()
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept(subprotocol="genlayer-auth")
    queue = await logs_store.subscribe(wallet_address=wallet_address)
    try:
        # Send a small backlog so users immediately see context.
        backlog = await logs_store.recent(wallet_address=wallet_address, limit=30)
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
