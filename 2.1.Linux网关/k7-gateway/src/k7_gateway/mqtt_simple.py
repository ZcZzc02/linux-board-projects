"""Minimal MQTT v3.1.1 publisher using only the Python standard library."""

from __future__ import annotations

import socket
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


@dataclass
class MqttPublisher:
    host: str
    port: int
    client_id: str
    keepalive: int = 60
    timeout: float = 10.0

    _sock: socket.socket | None = None

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

    def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
        if self._sock is None:
            raise MqttError("MQTT publisher is not connected")
        self._sock.sendall(build_publish_packet(topic, payload, retain=retain))

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
