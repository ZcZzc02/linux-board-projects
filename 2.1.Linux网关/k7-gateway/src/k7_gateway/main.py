"""Command line entry for K7 gateway bring-up."""

from __future__ import annotations

import argparse
import json
import sys
import time

from .board_check import run_checks
from .config import DEFAULT_LORA_BAUD, DEFAULT_LORA_DEVICE, NODE_COUNT
from .e22 import read_config
from .gateway import run_lora_gateway
from .lora_protocol import LoRaFrameError, extract_frames, mqtt_message_for_frame, parse_frame


def cmd_self_check(args: argparse.Namespace) -> int:
    checks = run_checks()
    for item in checks:
        status = "OK" if item.ok else "FAIL"
        print(f"[{status}] {item.name}: {item.detail}")
    return 0 if all(item.ok for item in checks[:4]) else 1


def cmd_e22_read_config(args: argparse.Namespace) -> int:
    result = read_config(args.device, args.baud, args.timeout)
    for line in result.as_lines():
        print(line)
    return 0 if result.ok else 1


def cmd_parse_hex(args: argparse.Namespace) -> int:
    raw = bytes.fromhex(args.hex)
    try:
        frame = parse_frame(raw, node_count=args.node_count)
        topic, payload = mqtt_message_for_frame(frame)
    except LoRaFrameError as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        return 1
    print(f"TOPIC={topic}")
    print(f"PAYLOAD={payload}")
    return 0


def cmd_listen_lora(args: argparse.Namespace) -> int:
    from .serial_posix import SerialPort

    buffer = b""
    end = time.monotonic() + args.seconds
    print(f"Listening {args.device} at {args.baud} for {args.seconds}s")
    with SerialPort.open(args.device, args.baud) as port:
        while time.monotonic() < end:
            chunk = port.read_for(0.5)
            if not chunk:
                continue
            if args.raw:
                print(f"RX_HEX={chunk.hex().upper()}")
            buffer += chunk
            frames, buffer = extract_frames(buffer, node_count=args.node_count)
            for frame in frames:
                topic, payload = mqtt_message_for_frame(frame)
                print(json.dumps({"topic": topic, "payload": json.loads(payload)}, ensure_ascii=False))
    if buffer:
        print(f"LEFTOVER_HEX={buffer.hex().upper()}")
    return 0


def cmd_run_lora(args: argparse.Namespace) -> int:
    return run_lora_gateway(
        device=args.device,
        baud=args.baud,
        node_count=args.node_count,
        log_path=args.log,
        raw_log_path=args.raw_log,
        seconds=args.seconds,
        echo=not args.quiet,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        mqtt_client_id=args.mqtt_client_id,
        transport=args.transport,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="k7-gateway")
    sub = parser.add_subparsers(dest="command", required=True)

    self_check = sub.add_parser("self-check", help="check K7 UART3 and network baseline")
    self_check.set_defaults(func=cmd_self_check)

    e22 = sub.add_parser("e22-read-config", help="read E22 register configuration")
    e22.add_argument("--device", default=DEFAULT_LORA_DEVICE)
    e22.add_argument("--baud", type=int, default=DEFAULT_LORA_BAUD)
    e22.add_argument("--timeout", type=float, default=3.0)
    e22.set_defaults(func=cmd_e22_read_config)

    parse_hex = sub.add_parser("parse-hex", help="parse one LoRa frame from hex")
    parse_hex.add_argument("hex")
    parse_hex.add_argument("--node-count", type=int, default=NODE_COUNT)
    parse_hex.set_defaults(func=cmd_parse_hex)

    listen = sub.add_parser("listen-lora", help="listen and parse LoRa frames")
    listen.add_argument("--device", default=DEFAULT_LORA_DEVICE)
    listen.add_argument("--baud", type=int, default=DEFAULT_LORA_BAUD)
    listen.add_argument("--seconds", type=float, default=60.0)
    listen.add_argument("--node-count", type=int, default=NODE_COUNT)
    listen.add_argument("--raw", action="store_true")
    listen.set_defaults(func=cmd_listen_lora)

    run_lora = sub.add_parser("run-lora", help="run LoRa receiver and write JSONL logs")
    run_lora.add_argument("--device", default=DEFAULT_LORA_DEVICE)
    run_lora.add_argument("--baud", type=int, default=DEFAULT_LORA_BAUD)
    run_lora.add_argument("--node-count", type=int, default=NODE_COUNT)
    run_lora.add_argument("--log", default="/var/log/k7-gateway/lora.jsonl")
    run_lora.add_argument("--raw-log", default=None)
    run_lora.add_argument("--seconds", type=float, default=None)
    run_lora.add_argument("--quiet", action="store_true", help="do not echo JSON records to stdout")
    run_lora.add_argument("--mqtt-broker", default=None, help="publish parsed records to this MQTT broker")
    run_lora.add_argument("--mqtt-port", type=int, default=1883)
    run_lora.add_argument("--mqtt-client-id", default="k7-gateway-GW001")
    run_lora.add_argument("--transport", default="wifi", choices=["wifi", "4g", "5g"])
    run_lora.set_defaults(func=cmd_run_lora)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
