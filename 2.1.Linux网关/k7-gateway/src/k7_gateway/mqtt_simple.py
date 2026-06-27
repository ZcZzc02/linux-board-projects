"""Minimal MQTT v3.1.1 client using only the Python standard library."""

from __future__ import annotations

import select
import socket
import time
from dataclasses import dataclass


class MqttError(RuntimeError):
    """Raised when the MQTT broker rejects or drops the connection."""


def encode_remaining_length(value: int) -> bytes:
    if value < 0 or value > 268_435_455:
        raise ValueError("remaining length out of range")
    encoded = bytearray()
    while True:
        byte = value % 128
        value //= 128
        if value > 0:
            byte |= 0x80
        encoded.append(byte)
        if value == 0:
            return bytes(encoded)


def encode_utf8(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 65535:
        raise ValueError("MQTT string is too long")
    return len(raw).to_bytes(2, "big") + raw


def build_connect_packet(
    *,
    client_id: str,
    keepalive: int,
    will_topic: str | None = None,
    will_payload: str | None = None,
) -> bytes:
    flags = 0x02  # clean session
    payload = bytearray()
    payload += encode_utf8(client_id)
    if will_topic is not None and will_payload is not None:
        flags |= 0x04
        payload += encode_utf8(will_topic)
        payload += encode_utf8(will_payload)

    variable_header = (
        encode_utf8("MQTT")
        + bytes([0x04, flags])
        + int(keepalive).to_bytes(2, "big")
    )
    remaining = variable_header + payload
    return bytes([0x10]) + encode_remaining_length(len(remaining)) + remaining


def build_publish_packet(topic: str, payload: str, *, retain: bool = False) -> bytes:
    payload_bytes = payload.encode("utf-8")
    variable_header = encode_utf8(topic)
    header = 0x31 if retain else 0x30
    remaining = variable_header + payload_bytes
    return bytes([header]) + encode_remaining_length(len(remaining)) + remaining


def build_subscribe_packet(topic: str, *, packet_id: int, qos: int = 1) -> bytes:
    if packet_id < 1 or packet_id > 65535:
        raise ValueError("packet_id out of range")
    if qos not in (0, 1):
        raise ValueError("only QoS 0/1 subscriptions are supported")
    variable_header = packet_id.to_bytes(2, "big")
    payload = encode_utf8(topic) + bytes([qos])
    remaining = variable_header + payload
    return b"\x82" + encode_remaining_length(len(remaining)) + remaining


def build_puback_packet(packet_id: int) -> bytes:
    if packet_id < 1 or packet_id > 65535:
        raise ValueError("packet_id out of range")
    return b"\x40\x02" + packet_id.to_bytes(2, "big")


@dataclass(frozen=True)
class MqttMessage:
    topic: str
    payload: bytes
    qos: int
    packet_id: int | None = None


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise MqttError("MQTT connection closed")
        chunks.extend(chunk)
    return bytes(chunks)


def _recv_remaining_length(sock: socket.socket) -> tuple[int, bytes]:
    multiplier = 1
    value = 0
    encoded = bytearray()
    while True:
        byte = _recv_exact(sock, 1)[0]
        encoded.append(byte)
        value += (byte & 0x7F) * multiplier
        if (byte & 0x80) == 0:
            return value, bytes(encoded)
        multiplier *= 128
        if multiplier > 128 * 128 * 128:
            raise MqttError("malformed remaining length")


def _decode_utf8(data: bytes, offset: int = 0) -> tuple[str, int]:
    if offset + 2 > len(data):
        raise MqttError("malformed MQTT string")
    length = int.from_bytes(data[offset : offset + 2], "big")
    start = offset + 2
    end = start + length
    if end > len(data):
        raise MqttError("malformed MQTT string")
    return data[start:end].decode("utf-8"), end


@dataclass
class MqttPublisher:
    host: str
    port: int
    client_id: str
    keepalive: int = 60
    timeout: float = 10.0

    _sock: socket.socket | None = None
    _next_packet_id: int = 1
    _last_io: float = 0.0

    def connect(self, *, will_topic: str | None = None, will_payload: str | None = None) -> None:
        self.close()
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        sock.sendall(
            build_connect_packet(
                client_id=self.client_id,
                keepalive=self.keepalive,
                will_topic=will_topic,
                will_payload=will_payload,
            )
        )
        resp = sock.recv(4)
        if len(resp) != 4 or resp[0] != 0x20 or resp[1] != 0x02 or resp[3] != 0x00:
            sock.close()
            raise MqttError(f"MQTT CONNACK rejected: {resp.hex().upper()}")
        self._sock = sock
        self._last_io = time.monotonic()

    def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
        if self._sock is None:
            raise MqttError("MQTT publisher is not connected")
        self._sock.sendall(build_publish_packet(topic, payload, retain=retain))
        self._last_io = time.monotonic()

    def subscribe(self, topic: str, *, qos: int = 1) -> None:
        if self._sock is None:
            raise MqttError("MQTT client is not connected")
        packet_id = self._allocate_packet_id()
        self._sock.sendall(build_subscribe_packet(topic, packet_id=packet_id, qos=qos))
        self._last_io = time.monotonic()
        packet_type, _, payload = self._read_packet(timeout=self.timeout)
        if packet_type != 9 or len(payload) < 3:
            raise MqttError("MQTT SUBACK not received")
        suback_id = int.from_bytes(payload[:2], "big")
        if suback_id != packet_id:
            raise MqttError(f"MQTT SUBACK packet id mismatch: {suback_id}")
        if payload[2] == 0x80:
            raise MqttError("MQTT SUBSCRIBE rejected")

    def poll(self, timeout: float = 0.0) -> list[MqttMessage]:
        if self._sock is None:
            raise MqttError("MQTT client is not connected")
        messages: list[MqttMessage] = []
        while True:
            ready, _, _ = select.select([self._sock], [], [], timeout)
            timeout = 0.0
            if not ready:
                self.ping_if_idle()
                return messages

            packet_type, flags, payload = self._read_packet(timeout=self.timeout)
            self._last_io = time.monotonic()
            if packet_type == 3:
                message = self._parse_publish(flags, payload)
                if message.packet_id is not None:
                    self._sock.sendall(build_puback_packet(message.packet_id))
                messages.append(message)
            elif packet_type in (4, 9, 13):
                continue
            else:
                continue

    def ping_if_idle(self) -> None:
        if self._sock is None:
            return
        if time.monotonic() - self._last_io >= max(5, self.keepalive // 2):
            self._sock.sendall(b"\xC0\x00")
            self._last_io = time.monotonic()

    def _allocate_packet_id(self) -> int:
        packet_id = self._next_packet_id
        self._next_packet_id += 1
        if self._next_packet_id > 65535:
            self._next_packet_id = 1
        return packet_id

    def _read_packet(self, *, timeout: float) -> tuple[int, int, bytes]:
        if self._sock is None:
            raise MqttError("MQTT client is not connected")
        old_timeout = self._sock.gettimeout()
        self._sock.settimeout(timeout)
        try:
            fixed = _recv_exact(self._sock, 1)[0]
            remaining_length, _ = _recv_remaining_length(self._sock)
            payload = _recv_exact(self._sock, remaining_length)
        finally:
            self._sock.settimeout(old_timeout)
        return fixed >> 4, fixed & 0x0F, payload

    def _parse_publish(self, flags: int, payload: bytes) -> MqttMessage:
        topic, offset = _decode_utf8(payload, 0)
        qos = (flags >> 1) & 0x03
        packet_id: int | None = None
        if qos:
            if offset + 2 > len(payload):
                raise MqttError("malformed MQTT publish packet")
            packet_id = int.from_bytes(payload[offset : offset + 2], "big")
            offset += 2
        return MqttMessage(topic=topic, payload=payload[offset:], qos=qos, packet_id=packet_id)

    def close(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.sendall(b"\xE0\x00")
        except OSError:
            pass
        try:
            self._sock.close()
        finally:
            self._sock = None
