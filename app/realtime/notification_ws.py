from __future__ import annotations

from collections import defaultdict
import logging
from typing import Any

from fastapi import WebSocket


logger = logging.getLogger("notification_ws")


class NotificationWSManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        if user_id in self._connections and websocket in self._connections[user_id]:
            self._connections[user_id].remove(websocket)
        if user_id in self._connections and not self._connections[user_id]:
            self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        sockets = list(self._connections.get(user_id, set()))
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception as exc:
                logger.warning("Falha ao enviar WS para usuário %s: %s", user_id, exc)
                self.disconnect(user_id, ws)


notification_manager = NotificationWSManager()
