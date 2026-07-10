"""
mqtt_client.py — MQTT 订阅逻辑
使用 paho-mqtt，在后台线程运行，通过回调写库并广播 WebSocket
"""
import json
import base64
import time
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE,
    MQTT_SUBSCRIBE_TOPICS, MQTT_CMD_TOPIC, MQTT_TOPIC_PREFIX,
    MQTT_USE_TLS, MQTT_USERNAME, MQTT_PASSWORD,
)
from frame_parser import parse_frame

logger = logging.getLogger("mqtt")

# 全局广播函数（由 main.py 注入，用于推送 WebSocket）
_broadcast_fn = None
# 全局数据库写入函数（由 main.py 注入）
_save_frame_fn = None

# 连接状态追踪
_server_mqtt_connected = False   # 上位机 → HiveMQ 是否已连接
_gw_online = False               # 网关最后汇报的在线状态
_gw_last_seen: datetime | None = None  # 网关最后收到任何消息的时间
_gw_transport: str | None = None        # wifi / 4g / 5g / None


def _normalize_transport(value) -> str | None:
    if value is None:
        return None
    transport = str(value).strip().lower()
    if transport == "cat1":
        return "4g"
    if transport in {"wifi", "4g", "5g"}:
        return transport
    return None


def set_broadcast(fn):
    global _broadcast_fn
    _broadcast_fn = fn


def set_save_frame(fn):
    global _save_frame_fn
    _save_frame_fn = fn


def on_connect(client, userdata, flags, rc, props=None):
    global _server_mqtt_connected
    if rc == 0:
        _server_mqtt_connected = True
        logger.info(f"已连接到 MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        for topic in MQTT_SUBSCRIBE_TOPICS:
            client.subscribe(topic, qos=1)
            logger.info(f"已订阅 topic: {topic}")
        from routers.realtime import update_status
        update_status("server_mqtt", True)
        if _broadcast_fn:
            _broadcast_fn({"type": "server_mqtt", "connected": True,
                           "ts": datetime.now(timezone.utc).isoformat()})
    else:
        logger.error(f"MQTT 连接失败，返回码: {rc}")


def on_disconnect(client, userdata, rc, props=None, reason=None):
    global _server_mqtt_connected
    _server_mqtt_connected = False
    logger.warning(f"MQTT 连接断开 (rc={rc})，将自动重连...")
    from routers.realtime import update_status
    update_status("server_mqtt", False)
    if _broadcast_fn:
        _broadcast_fn({"type": "server_mqtt", "connected": False,
                       "ts": datetime.now(timezone.utc).isoformat()})


def on_message(client, userdata, msg):
    global _gw_online, _gw_last_seen, _gw_transport
    topic = msg.topic
    payload_bytes = msg.payload

    logger.info(f"收到消息 topic={topic} len={len(payload_bytes)}")

    # 更新网关最后在线时间（任何来自订阅 topic 的消息都视为网关活跃）
    now = datetime.now(timezone.utc)

    # 处理网关连接状态消息（直接返回，不当帧解析）
    if topic == f"{MQTT_TOPIC_PREFIX}/status/gw":
        try:
            status = json.loads(payload_bytes.decode("utf-8"))
            gw_online = bool(status.get("online", 0))
            gw_transport = _normalize_transport(status.get("transport"))
        except Exception:
            if msg.retain:
                logger.warning("ignore retained invalid gateway status")
                return
            gw_online = True
            gw_transport = None

        if msg.retain and gw_online:
            logger.info("ignore retained gateway online status; waiting for live gateway message")
            return

        _gw_online = gw_online
        _gw_transport = gw_transport if _gw_online else None
        _gw_last_seen = now if not msg.retain else None
        from routers.realtime import update_status
        update_status("gw_online", _gw_online)
        update_status("gw_transport", _gw_transport)
        if _broadcast_fn:
            _broadcast_fn({"type": "gw_status", "online": _gw_online,
                           "transport": _gw_transport,
                           "ts": now.isoformat()})
        return

    # 处理节点状态消息
    if "/status/node/" in topic:
        try:
            if not msg.retain:
                _gw_last_seen = now
            status = json.loads(payload_bytes.decode("utf-8"))
            node_id = topic.split("/")[-1]
            if _broadcast_fn:
                _broadcast_fn({"type": "node_status", "node_id": node_id,
                               "online": bool(status.get("online", 0)),
                               "ts": datetime.now(timezone.utc).isoformat()})
        except Exception:
            pass
        return

    if not msg.retain:
        _gw_last_seen = now

    # 收到任何节点数据消息（非 retained），说明网关在线（兼容服务器晚于网关启动的场景）
    # msg.retain=True 表示这是 broker 缓存的旧消息，不能作为网关当前在线的依据
    if "/data/node/" in topic and not _gw_online and not msg.retain:
        _gw_online = True
        logger.info("收到节点数据（非retained），自动标记网关在线")
        from routers.realtime import update_status
        update_status("gw_online", True)
        if _broadcast_fn:
            _broadcast_fn({"type": "gw_status", "online": True,
                           "transport": _gw_transport,
                           "ts": datetime.now(timezone.utc).isoformat()})

    # 1a. CAN JSON 格式：{"ts":...,"id":"600","dlc":8,"data":"0011..."}
    if topic.endswith("/can"):
        try:
            j = json.loads(payload_bytes.decode("utf-8"))
            if "id" in j and "dlc" in j and "data" in j:
                try:
                    node_addr_int = int(topic.split("/")[-2])
                except (ValueError, IndexError):
                    node_addr_int = 0
                parsed = {
                    "node_addr": node_addr_int,
                    "frame_type": 0x02,
                    "type_name": "CAN",
                    "crc_ok": True,
                    "can_id": str(j["id"]).upper(),
                    "can_dlc": int(j["dlc"]),
                    "can_data": str(j["data"]).upper(),
                }
                record = {
                    "ts": datetime.utcnow().isoformat(),
                    "topic": topic,
                    "raw_hex": str(j.get("data", "")).upper(),
                    "parsed": parsed,
                }
                if _broadcast_fn:
                    _broadcast_fn(record)
                if _save_frame_fn:
                    _save_frame_fn(record)
                return
        except Exception:
            pass

    # 1b. RS485 JSON 格式：{"ts":...,"voltage":N,"current":N,"soc":N,"raw3":N}
    if topic.endswith("/rs485"):
        try:
            j = json.loads(payload_bytes.decode("utf-8"))
            if "voltage" in j or "current" in j:
                try:
                    node_addr_int = int(topic.split("/")[-2])
                except (ValueError, IndexError):
                    node_addr_int = 0
                voltage = j.get("voltage", 0)
                current = j.get("current", 0)
                soc     = j.get("soc", 0)
                raw3    = j.get("raw3", 0)
                parsed = {
                    "node_addr": node_addr_int,
                    "frame_type": 0x03,
                    "type_name": "RS485",
                    "crc_ok": True,
                    "voltage": voltage,
                    "current": current,
                    "soc": soc,
                    "raw3": raw3,
                    "payload_hex": f"{voltage:04X}{current:04X}{soc:04X}{raw3:04X}",
                }
                record = {
                    "ts": datetime.utcnow().isoformat(),
                    "topic": topic,
                    "raw_hex": parsed["payload_hex"],
                    "parsed": parsed,
                }
                if _broadcast_fn:
                    _broadcast_fn(record)
                if _save_frame_fn:
                    _save_frame_fn(record)
                return
        except Exception:
            pass

    # 1c. 尝试 JSON 包装（网关上报格式：{"raw":"AABBCC..."}，AD7606 用此格式）
    raw_bytes = None
    try:
        payload_json = json.loads(payload_bytes.decode("utf-8"))
        raw_hex = payload_json.get("raw", "")
        if raw_hex:
            raw_bytes = bytes.fromhex(raw_hex)
    except Exception:
        pass

    # 2. 尝试 Base64 编码帧（HiveMQ 网页工具 / 部分网关上报）
    if raw_bytes is None:
        try:
            candidate = base64.b64decode(payload_bytes)
            if parse_frame(candidate) is not None:
                raw_bytes = candidate
                logger.info("payload 识别为 Base64 编码帧")
        except Exception:
            pass

    # 3. 原始二进制帧（真实硬件直接上报）
    if raw_bytes is None:
        raw_bytes = payload_bytes

    # 解析帧
    parsed = None
    if raw_bytes:
        parsed = parse_frame(raw_bytes)

    # 构建推送数据
    record = {
        "ts": datetime.utcnow().isoformat(),
        "topic": topic,
        "raw_hex": raw_bytes.hex().upper() if raw_bytes else payload_bytes.hex().upper(),
        "parsed": parsed,
    }

    # 广播到 WebSocket
    if _broadcast_fn:
        _broadcast_fn(record)

    # 写入数据库（异步，由注入的函数处理）
    if _save_frame_fn and parsed:
        _save_frame_fn(record)


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(
        client_id=f"daq-server-{int(time.time())}",
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=3, max_delay=30)
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_USE_TLS:
        client.tls_set()  # 使用系统 CA，HiveMQ Cloud 证书由公共 CA 签发
    return client


def publish_command(client: mqtt.Client, node_id: str, cmd: dict):
    """下发指令到指定节点"""
    topic = MQTT_CMD_TOPIC.format(node_id=node_id)
    payload = json.dumps(cmd, separators=(',', ':'))  # 紧凑格式，避免超网关MQTT缓冲区
    client.publish(topic, payload, qos=1)
    logger.info(f"已下发指令 topic={topic} payload={payload}")
