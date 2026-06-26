"""Shared configuration copied from the old STM32 gateway."""

from __future__ import annotations

DEFAULT_LORA_DEVICE = "/dev/ttyS3"
DEFAULT_LORA_BAUD = 9600

MQTT_SERVER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "GW001_fengyan"
MQTT_TOPIC_PREFIX = "fengyan_daq_2026"

NODE_COUNT = 1

E22_READ_CONFIG_CMD = bytes.fromhex("C1 00 09")
E22_EXPECTED_CONFIG = bytes.fromhex("C1 00 09 00 00 00 65 00 17 0B 00 00")

UART3_DT_STATUS = "/sys/firmware/devicetree/base/serial@2ad60000/status"
I2C7_DT_STATUS = "/sys/firmware/devicetree/base/i2c@2aca0000/status"
K7_4G_DIAL_SCRIPT = "/usr/bin/4G_dialing.sh"
K7_QUECTEL_CM = "/usr/bin/quectel-CM"
