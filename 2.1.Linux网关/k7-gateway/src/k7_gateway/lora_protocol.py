"""LoRa frame parser compatible with the old STM32 gateway."""

from __future__ import annotations

import json
import struct
import time
from dataclasses import dataclass
from enum import IntEnum

from .config import MQTT_TOPIC_PREFIX, NODE_COUNT


class LoRaType(IntEnum):
    AD7606 = 0x01
    CAN = 0x02
    RS485 = 0x03


class LoRaFrameError(ValueError):
    """Raised when a LoRa frame is malformed."""


@dataclass(frozen=True)
class LoRaFrame:
    node_addr: int
    frame_type: int
    payload: bytes
    crc: int
    raw: bytes

    @property
    def topic(self) -> str:
        suffix = {
            LoRaType.AD7606: "ad7606",
            LoRaType.CAN: "can",
            LoRaType.RS485: "rs485",
        }.get(LoRaType(self.frame_type) if self.frame_type in LoRaType._value2member_map_ else None)
        if suffix is None:
            return f"{MQTT_TOPIC_PREFIX}/data/node/{self.node_addr}/unknown"
        return f"{MQTT_TOPIC_PREFIX}/data/node/{self.node_addr}/{suffix}"


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
            crc &= 0xFFFF
    return crc


def append_crc(frame_without_crc: bytes) -> bytes:
    crc = crc16_modbus(frame_without_crc)
    return frame_without_crc + bytes([(crc >> 8) & 0xFF, crc & 0xFF])


def parse_frame(data: bytes, *, node_count: int = NODE_COUNT) -> LoRaFrame:
    if len(data) < 5:
        raise LoRaFrameError("frame too short")

    node_addr = data[0]
    frame_type = data[1]
    payload_len = data[2]
    expected_len = 3 + payload_len + 2
    if len(data) < expected_len:
        raise LoRaFrameError(f"incomplete frame: need {expected_len}, got {len(data)}")
    if len(data) > expected_len:
        data = data[:expected_len]

    if node_addr < 1 or node_addr > node_count:
        raise LoRaFrameError(f"node address out of range: {node_addr}")

    crc_calc = crc16_modbus(data[: 3 + payload_len])
    crc_recv = (data[3 + payload_len] << 8) | data[3 + payload_len + 1]
    if crc_calc != crc_recv:
        raise LoRaFrameError(f"crc mismatch: calc=0x{crc_calc:04X} recv=0x{crc_recv:04X}")

    return LoRaFrame(
        node_addr=node_addr,
        frame_type=frame_type,
        payload=data[3 : 3 + payload_len],
        crc=crc_recv,
        raw=data,
    )


def decode_payload(frame: LoRaFrame, *, now_ms: int | None = None) -> dict[str, object]:
    timestamp = int(time.time() * 1000) if now_ms is None else now_ms

    if frame.frame_type == LoRaType.AD7606:
        if len(frame.payload) < 16:
            raise LoRaFrameError("AD7606 payload must be at least 16 bytes")
        raw_values = list(struct.unpack(">8h", frame.payload[:16]))
        millivolts = [value * 5000.0 / 32767.0 for value in raw_values]
        return {
            "ts": timestamp,
            "raw": frame.raw.hex().upper(),
            "channels_raw": raw_values,
            "channels_mv": [round(value, 1) for value in millivolts],
        }

    if frame.frame_type == LoRaType.CAN:
        if len(frame.payload) < 11:
            raise LoRaFrameError("CAN payload must be at least 11 bytes")
        can_id = (frame.payload[0] << 8) | frame.payload[1]
        dlc = frame.payload[2]
        if dlc > 8:
            raise LoRaFrameError(f"CAN dlc out of range: {dlc}")
        can_data = frame.payload[3 : 3 + dlc]
        return {
            "ts": timestamp,
            "id": f"{can_id:03X}",
            "dlc": dlc,
            "data": can_data.hex().upper(),
        }

    if frame.frame_type == LoRaType.RS485:
        if len(frame.payload) < 8:
            raise LoRaFrameError("RS485 payload must be at least 8 bytes")
        regs = list(struct.unpack(">4H", frame.payload[:8]))
        return {
            "ts": timestamp,
            "voltage": regs[0],
            "current": regs[1],
            "soc": regs[2],
            "raw3": regs[3],
        }

    return {"ts": timestamp, "raw": frame.raw.hex().upper()}


def mqtt_message_for_frame(frame: LoRaFrame, *, now_ms: int | None = None) -> tuple[str, str]:
    payload = decode_payload(frame, now_ms=now_ms)
    return frame.topic, json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def extract_frames(buffer: bytes, *, node_count: int = NODE_COUNT) -> tuple[list[LoRaFrame], bytes]:
    frames: list[LoRaFrame] = []
    idx = 0
    while idx + 5 <= len(buffer):
        payload_len = buffer[idx + 2]
        frame_len = 3 + payload_len + 2
        if idx + frame_len > len(buffer):
            break
        candidate = buffer[idx : idx + frame_len]
        try:
            frames.append(parse_frame(candidate, node_count=node_count))
            idx += frame_len
        except LoRaFrameError:
            idx += 1
    return frames, buffer[idx:]
