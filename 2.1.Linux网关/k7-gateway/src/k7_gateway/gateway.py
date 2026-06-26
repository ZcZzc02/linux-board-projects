"""Runtime loop for receiving LoRa frames on the K7 gateway."""

from __future__ import annotations

import json
import sys
import time
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from .config import MQTT_TOPIC_PREFIX
from .lora_protocol import extract_frames, mqtt_message_for_frame
from .mqtt_simple import MqttPublisher


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
    transport: str = "wifi",
) -> int:
    from .serial_posix import SerialPort

    buffer = b""
    publisher: MqttPublisher | None = None
    status_topic = f"{MQTT_TOPIC_PREFIX}/status/gw"
    end = None if seconds is None else time.monotonic() + seconds
    print(f"Running LoRa gateway on {device} at {baud}")
    if log_path:
        print(f"JSONL_LOG={log_path}")
    if raw_log_path:
        print(f"RAW_LOG={raw_log_path}")
    if mqtt_broker:
        publisher = MqttPublisher(mqtt_broker, mqtt_port, mqtt_client_id)
        offline_payload = json.dumps(
            {"online": 0, "transport": transport}, separators=(",", ":")
        )
        publisher.connect(will_topic=status_topic, will_payload=offline_payload)
        publisher.publish(
            status_topic,
            json.dumps({"online": 1, "transport": transport}, separators=(",", ":")),
        )
        print(f"MQTT_BROKER={mqtt_broker}:{mqtt_port}")

    try:
        with SerialPort.open(device, baud) as port:
            with _open_append(log_path) as log_file, _open_append(raw_log_path) as raw_file:
                while end is None or time.monotonic() < end:
                    chunk = port.read_for(0.5)
                    if not chunk:
                        continue
                    if raw_file:
                        raw_file.write(f"{int(time.time() * 1000)} {chunk.hex().upper()}\n")

                    records, buffer = records_from_chunk(buffer, chunk, node_count=node_count)
                    for record in records:
                        payload = json.dumps(record.payload, ensure_ascii=False, separators=(",", ":"))
                        if publisher:
                            publisher.publish(record.topic, payload)
                        line = record.to_json_line()
                        if log_file:
                            log_file.write(line + "\n")
                        if echo:
                            print(line)
    finally:
        if publisher:
            try:
                publisher.publish(
                    status_topic,
                    json.dumps({"online": 0, "transport": transport}, separators=(",", ":")),
                )
            except Exception as exc:
                print(f"MQTT_OFFLINE_STATUS_ERROR={exc}", file=sys.stderr)
            publisher.close()

    if buffer:
        print(f"LEFTOVER_HEX={buffer.hex().upper()}")
    return 0
