"""
routers/commands.py — 指令下发 API
支持：通用 MQTT 指令、RS485 读写、PCS 控制预设、透传
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api", tags=["commands"])

# MQTT 客户端实例（由 main.py 注入）
_mqtt_client = None


def set_mqtt_client(client):
    global _mqtt_client
    _mqtt_client = client


class CommandRequest(BaseModel):
    node_id: str
    cmd: str
    params: dict[str, Any] = {}


# 需要 power_w 参数的预设指令集合
_POWER_CMDS = {"set_charge_power", "set_discharge_power"}

# 所有合法指令（白名单，防止任意指令注入）
_VALID_CMDS = {
    # 通用
    "ping", "reset",
    # RS485
    "rs485_write", "rs485_read", "rs485_raw",
    # PCS 控制
    "set_charge_power", "set_discharge_power",
    "enable_charge", "disable_charge",
    "enable_discharge", "disable_discharge",
    # 透传
    "relay",
}


@router.post("/command")
async def send_command(req: CommandRequest):
    """向指定节点下发指令（通过 MQTT cmd topic）"""
    if _mqtt_client is None:
        raise HTTPException(status_code=503, detail="MQTT 客户端未就绪")

    if req.cmd not in _VALID_CMDS:
        raise HTTPException(status_code=400, detail=f"不支持的指令：{req.cmd}")

    from mqtt_client import publish_command
    publish_command(_mqtt_client, req.node_id, {"cmd": req.cmd, "params": req.params})
    return {"status": "ok", "node_id": req.node_id, "cmd": req.cmd, "params": req.params}
