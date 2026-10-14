# app/routes/ws_notifications.py
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.core.ws_manager import manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/notifications")
async def notifications_websocket(websocket: WebSocket, token: str):
    """
    Connect with: ws://localhost:8001/ws/notifications?token=<access_token>
    WebSockets can't send an Authorization header during the handshake in
    most browser clients, so the JWT is passed as a query param instead —
    this is the standard workaround for WS auth.
    """
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        await websocket.close(code=4001)
        return

    user_id = uuid.UUID(payload["sub"])
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep the connection alive; we don't act on client messages
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)