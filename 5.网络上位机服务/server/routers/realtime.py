"""
routers/realtime.py — WebSocket 实时推送
"""
import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("ws")
router = APIRouter(tags=["realtime"])

# 所有已连接的 WebSocket 客户端
_connections: Set[WebSocket] = set()
# asyncio 事件循环引用（由 main.py 写入）
_loop: asyncio.AbstractEventLoop | None = None
# 当前各组件状态（由 mqtt_client 写入）
_current_status: dict = {"server_mqtt": False, "gw_online": False, "gw_transport": None}


def set_loop(loop: asyncio.AbstractEventLoop):
    global _loop
    _loop = loop


def update_status(key: str, value):
    """mqtt_client 调用，更新当前连接状态"""
    _current_status[key] = value


def broadcast(data: dict):
    """
    从 MQTT 回调线程（非 asyncio 线程）安全地广播消息。
    使用 run_coroutine_threadsafe 跨线程投递。
    """
    if _loop and _connections:
        asyncio.run_coroutine_threadsafe(_async_broadcast(data), _loop)


async def _async_broadcast(data: dict):
    msg = json.dumps(data, ensure_ascii=False, default=str)
    dead = set()
    for ws in list(_connections):
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    logger.info(f"WebSocket 客户端连接，当前共 {len(_connections)} 个")
    # 新客户端连接后立即推送当前实际状态（避免错过已触发的广播）
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await websocket.send_text(json.dumps({
            "type": "server_mqtt",
            "connected": _current_status.get("server_mqtt", False),
            "ts": now
        }))
        await websocket.send_text(json.dumps({
            "type": "gw_status",
            "online": _current_status.get("gw_online", False),
            "transport": _current_status.get("gw_transport"),
            "ts": now
        }))
    except Exception:
        pass
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _connections.discard(websocket)
        logger.info(f"WebSocket 客户端断开，当前共 {len(_connections)} 个")
