# app/core/ws_manager.py
import uuid

from fastapi import WebSocket


class ConnectionManager:
    """
    Tracks active WebSocket connections per user_id, so we can push a
    notification directly to a specific logged-in user's open connection(s).
    One user could have multiple tabs/devices open, hence a LIST per user.
    """

    def __init__(self) -> None:
        self.active_connections: dict[uuid.UUID, list[WebSocket]] = {}

    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        connections = self.active_connections.get(user_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: uuid.UUID, message: dict) -> None:
        for connection in self.active_connections.get(user_id, []):
            await connection.send_json(message)


manager = ConnectionManager()