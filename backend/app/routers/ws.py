import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jwt import PyJWTError

from app.security.auth import decode_token
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/vagas")
async def ws_vagas(websocket: WebSocket, token: str = Query(...)) -> None:
    try:
        decode_token(token)
    except (PyJWTError, RuntimeError):
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
