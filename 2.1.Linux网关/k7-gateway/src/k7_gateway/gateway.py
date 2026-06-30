"""Runtime loop for receiving LoRa frames on the K7 gateway."""

from __future__ import annotations

import json
import sys
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from .config import MQTT_TOPIC_PREFIX
from .downlink import DownlinkCommandError, frame_from_command
from .lora_protocol import extract_frames, mqtt_message_for_frame
from .mqtt_simple import MqttPublisher
from .network_status import resolve_transport


@dataclass(frozen=True)
class GatewayRecord:
    topic: str
    payload: dict[str, object]

    def to_json_line(self) -> str:
        return json.dumps(
            {"topic": self.topic, "payload": self.payload},
            ensure_ascii=False,
            separators=(",", ":"),
        )


def records_from_chunk(
    buffer: bytes,
    chunk: bytes,
    *,
    node_count: int,
) -> tuple[list[GatewayRecord], bytes]:
    frames, leftover = extract_frames(buffer + chunk, node_count=node_count)
    records: list[GatewayRecord] = []
    for frame in frames:
        topic, payload_json = mqtt_message_for_frame(frame)
        records.append(GatewayRecord(topic=topic, payload=json.loads(payload_json)))
    return records, leftover


def _open_append(path: str | None):
    if not path:
        return nullcontext(None)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target.open("a", encoding="utf-8", buffering=1)


def run_lora_gateway(
    *,
    device: str,
    baud: int,
    node_count: int,
    log_path: str | None,
    raw_log_path: str | None,
    seconds: float | None,
    echo: bool,
    mqtt_broker: str | None = None,
    mqtt_port: int = 1883,
    mqtt_client_id: str = "k7-gateway-GW001",
    transport: str = "auto",
    status_interval: float = 10.0,
    mqtt_reconnect_interval: float = 10.0,
    mqtt_command_subscribe: bool = False,
) -> int:
    from .serial_posix import SerialPort

    buffer = b""
    publisher: MqttPublisher | None = None
    mqtt_connected = False
    next_mqtt_connect_at = 0.0
    status_topic = f"{MQTT_TOPIC_PREFIX}/status/gw"
    last_status_transport: str | None = None
    next_status_at = 0.0
    end = None if seconds is None else time.monotonic() + seconds

    def mark_mqtt_disconnected(reason: Exception | str) -> None:
        nonlocal mqtt_connected, next_mqtt_connect_at, last_status_transport
        if publisher:
            publisher.close()
        mqtt_connected = False
        last_status_transport = None
        next_mqtt_connect_at = time.monotonic() + max(1.0, mqtt_reconnect_interval)
        print(f"MQTT_DISCONNECTED={reason}", file=sys.stderr)

    def safe_publish(topic: str, payload: str) -> bool:
        if not publisher or not mqtt_connected:
            return False
        try:
            publisher.publish(topic, payload)
            return True
        except Exception as exc:
            mark_mqtt_disconnected(exc)
            return False

    def publish_gateway_status(online: int, *, force: bool = False) -> None:
        nonlocal last_status_transport, next_status_at
        if not publisher or not mqtt_connected:
            return
        now = time.monotonic()
        current_transport = resolve_transport(transport)
        if (
            not force
            and online
            and current_transport == last_status_transport
            and now < next_status_at
        ):
            return
        ok = safe_publish(
            status_topic,
            json.dumps(
                {"online": online, "transport": current_transport},
                separators=(",", ":"),
            ),
        )
        if not ok:
            return
        last_status_transport = current_transport if online else None
        next_status_at = now + max(1.0, status_interval)

    def connect_mqtt_if_needed(*, force: bool = False) -> None:
        nonlocal mqtt_connected, next_mqtt_connect_at
        if not publisher or mqtt_connected:
            return
        now = time.monotonic()
        if not force and now < next_mqtt_connect_at:
            return
        current_transport = resolve_transport(transport)
        offline_payload = json.dumps(
            {"online": 0, "transport": current_transport}, separators=(",", ":")
        )
        try:
            publisher.connect(will_topic=status_topic, will_payload=offline_payload)
            mqtt_connected = True
            publish_gateway_status(1, force=True)
            print(f"MQTT_BROKER={mqtt_broker}:{mqtt_port}")
            if mqtt_command_subscribe:
                command_topic = f"{MQTT_TOPIC_PREFIX}/cmd/node/+"
                publisher.subscribe(command_topic, qos=1)
                print(f"MQTT_COMMAND_TOPIC={command_topic}")
        except Exception as exc:
            mark_mqtt_disconnected(exc)

    print(f"Running LoRa gateway on {device} at {baud}")
    if log_path:
        print(f"JSONL_LOG={log_path}")
    if raw_log_path:
        print(f"RAW_LOG={raw_log_path}")
    if mqtt_broker:
        publisher = MqttPublisher(mqtt_broker, mqtt_port, mqtt_client_id)
        connect_mqtt_if_needed(force=True)

    try:
        with SerialPort.open(device, baud) as port:
            with _open_append(log_path) as log_file, _open_append(raw_log_path) as raw_file:
                while end is None or time.monotonic() < end:
                    connect_mqtt_if_needed()
                    publish_gateway_status(1)
                    if publisher and mqtt_connected and mqtt_command_subscribe:
                        try:
                            messages = publisher.poll(0.0)
                        except Exception as exc:
                            mark_mqtt_disconnected(exc)
                            messages = []
                        for message in messages:
                            try:
                                frame = frame_from_command(
                                    message.topic,
                                    message.payload,
                                    node_count=node_count,
                                )
                            except DownlinkCommandError as exc:
                                print(f"DOWNLINK_COMMAND_ERROR={exc}", file=sys.stderr)
                                continue
                            port.write(frame.raw)
                            print(
                                f"DOWNLINK_SENT node={frame.node_id} cmd={frame.command} "
                                f"hex={frame.raw_hex}"
                            )

                    chunk = port.read_for(0.5)
                    if not chunk:
                        continue
                    if raw_file:
                        raw_file.write(f"{int(time.time() * 1000)} {chunk.hex().upper()}\n")

                    records, buffer = records_from_chunk(buffer, chunk, node_count=node_count)
                    for record in records:
                        payload = json.dumps(record.payload, ensure_ascii=False, separators=(",", ":"))
                        if publisher and mqtt_connected:
                            safe_publish(record.topic, payload)
                        line = record.to_json_line()
                        if log_file:
                            log_file.write(line + "\n")
                        if echo:
                            print(line)
    finally:
        if publisher and mqtt_connected:
            try:
                safe_publish(
                    status_topic,
                    json.dumps(
                        {"online": 0, "transport": resolve_transport(transport)},
                        separators=(",", ":"),
                    ),
                )
            except Exception as exc:
                print(f"MQTT_OFFLINE_STATUS_ERROR={exc}", file=sys.stderr)
            publisher.close()

    if buffer:
        print(f"LEFTOVER_HEX={buffer.hex().upper()}")
    return 0
