from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.notification_ws import notification_manager


router = APIRouter(prefix="/ws/notifications", tags=["notifications_ws"])


@router.websocket("/{user_id}")
async def notifications_socket(websocket: WebSocket, user_id: int):
    await notification_manager.connect(user_id, websocket)
    try:
        while True:
            # Cliente pode enviar ping para manter conexão viva.
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        notification_manager.disconnect(user_id, websocket)
