"""Build LoRa downlink frames from backend MQTT command messages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .config import MQTT_TOPIC_PREFIX, NODE_COUNT
from .lora_protocol import append_crc


class DownlinkCommandError(ValueError):
    """Raised when a backend command cannot be mapped to a LoRa frame."""


@dataclass(frozen=True)
class DownlinkFrame:
    node_id: int
    command: str
    raw: bytes

    @property
    def raw_hex(self) -> str:
        return self.raw.hex().upper()


def _parse_node_id(topic: str, *, node_count: int) -> int:
    prefix = f"{MQTT_TOPIC_PREFIX}/cmd/node/"
    if not topic.startswith(prefix):
        raise DownlinkCommandError(f"unexpected command topic: {topic}")
    node_text = topic[len(prefix) :].split("/", 1)[0]
    try:
        node_id = int(node_text, 10)
    except ValueError as exc:
        raise DownlinkCommandError(f"invalid node id: {node_text}") from exc
    if node_id < 1 or node_id > node_count:
        raise DownlinkCommandError(f"node id out of range: {node_id}")
    return node_id


def _clean_hex(value: Any) -> str:
    text = str(value or "")
    text = text.replace("0x", "").replace("0X", "")
    return re.sub(r"[^0-9a-fA-F]", "", text)


def _bytes_from_hex(value: Any, *, max_len: int | None = None) -> bytes:
    text = _clean_hex(value)
    if len(text) == 0:
        raise DownlinkCommandError("hex payload is empty")
    if len(text) % 2:
        raise DownlinkCommandError("hex payload length must be even")
    data = bytes.fromhex(text)
    if max_len is not None and len(data) > max_len:
        raise DownlinkCommandError(f"hex payload too long: {len(data)} > {max_len}")
    return data


def _int_param(params: dict[str, Any], name: str, *, default: int | None = None) -> int:
    value = params.get(name, default)
    if value is None:
        raise DownlinkCommandError(f"missing param: {name}")
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def _u16(value: int, *, name: str) -> bytes:
    if value < 0 or value > 0xFFFF:
        raise DownlinkCommandError(f"{name} out of range: {value}")
    return value.to_bytes(2, "big")


def build_rs485_raw_frame(node_id: int, inner: bytes) -> bytes:
    if not inner or len(inner) > 20:
        raise DownlinkCommandError("rs485_raw payload length must be 1..20 bytes")
    return append_crc(bytes([node_id, 0x41, len(inner)]) + inner)


def build_can_relay_frame(node_id: int, can_id: int, data: bytes, *, dlc: int | None = None) -> bytes:
    if can_id < 0 or can_id > 0x7FF:
        raise DownlinkCommandError(f"CAN id out of range: {can_id}")
    actual_dlc = len(data) if dlc is None else dlc
    if actual_dlc < 0 or actual_dlc > 8:
        raise DownlinkCommandError(f"CAN dlc out of range: {actual_dlc}")
    if len(data) < actual_dlc:
        raise DownlinkCommandError("CAN data shorter than dlc")
    payload = can_id.to_bytes(2, "big") + bytes([actual_dlc]) + data[:actual_dlc]
    return append_crc(bytes([node_id, 0x42, len(payload)]) + payload)


def build_rs485_read_frame(node_id: int, params: dict[str, Any]) -> bytes:
    reg = _int_param(params, "reg", default=0)
    count = _int_param(params, "count", default=1)
    return append_crc(bytes([node_id, 0x03]) + _u16(reg, name="reg") + _u16(count, name="count"))


def build_rs485_write_frame(node_id: int, params: dict[str, Any]) -> bytes:
    reg = _int_param(params, "reg", default=0)
    data = _bytes_from_hex(params.get("data", ""), max_len=2)
    if len(data) != 2:
        raise DownlinkCommandError("rs485_write data must be exactly 2 bytes")
    return append_crc(bytes([node_id, 0x06]) + _u16(reg, name="reg") + data)


def frame_from_command(topic: str, payload: bytes | str, *, node_count: int = NODE_COUNT) -> DownlinkFrame:
    node_id = _parse_node_id(topic, node_count=node_count)
    if isinstance(payload, bytes):
        payload_text = payload.decode("utf-8")
    else:
        payload_text = payload
    try:
        command = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise DownlinkCommandError("command payload is not valid JSON") from exc

    cmd = str(command.get("cmd", "")).strip()
    params = command.get("params") or {}
    if not isinstance(params, dict):
        raise DownlinkCommandError("params must be an object")

    if cmd == "rs485_raw":
        raw = build_rs485_raw_frame(node_id, _bytes_from_hex(params.get("hex", ""), max_len=20))
    elif cmd == "rs485_read":
        raw = build_rs485_read_frame(node_id, params)
    elif cmd == "rs485_write":
        raw = build_rs485_write_frame(node_id, params)
    elif cmd == "relay":
        bus = str(params.get("bus", "")).strip().lower()
        if bus == "can" or "can_id" in params:
            can_id = _int_param(params, "can_id")
            data = _bytes_from_hex(params.get("data", ""), max_len=8)
            dlc = _int_param(params, "dlc", default=len(data))
            raw = build_can_relay_frame(node_id, can_id, data, dlc=dlc)
        elif bus == "rs485":
            raw = build_rs485_raw_frame(node_id, _bytes_from_hex(params.get("hex") or params.get("data"), max_len=20))
        else:
            raise DownlinkCommandError(f"unsupported relay bus: {bus}")
    else:
        raise DownlinkCommandError(f"unsupported command: {cmd}")

    return DownlinkFrame(node_id=node_id, command=cmd, raw=raw)
