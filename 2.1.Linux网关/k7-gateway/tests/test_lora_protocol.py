import json
import unittest

from k7_gateway.lora_protocol import append_crc, crc16_modbus, extract_frames, mqtt_message_for_frame, parse_frame


class LoRaProtocolTest(unittest.TestCase):
    def test_crc16_modbus_known_vector(self):
        self.assertEqual(crc16_modbus(b"123456789"), 0x4B37)

    def test_parse_ad7606_frame(self):
        payload = bytes.fromhex("00010002000300040005000600070008")
        raw = append_crc(bytes([1, 0x01, len(payload)]) + payload)

        frame = parse_frame(raw)
        topic, message = mqtt_message_for_frame(frame, now_ms=123)
        body = json.loads(message)

        self.assertEqual(topic, "fengyan_daq_2026/data/node/1/ad7606")
        self.assertEqual(body["ts"], 123)
        self.assertEqual(body["channels_raw"][:2], [1, 2])

    def test_parse_can_frame(self):
        payload = bytes.fromhex("0123080102030405060708")
        raw = append_crc(bytes([1, 0x02, len(payload)]) + payload)

        frame = parse_frame(raw)
        topic, message = mqtt_message_for_frame(frame, now_ms=123)
        body = json.loads(message)

        self.assertEqual(topic, "fengyan_daq_2026/data/node/1/can")
        self.assertEqual(body["id"], "123")
        self.assertEqual(body["dlc"], 8)
        self.assertEqual(body["data"], "0102030405060708")

    def test_parse_rs485_frame(self):
        payload = bytes.fromhex("08980078005A0000")
        raw = append_crc(bytes([1, 0x03, len(payload)]) + payload)

        frame = parse_frame(raw)
        topic, message = mqtt_message_for_frame(frame, now_ms=123)
        body = json.loads(message)

        self.assertEqual(topic, "fengyan_daq_2026/data/node/1/rs485")
        self.assertEqual(body["voltage"], 2200)
        self.assertEqual(body["current"], 120)
        self.assertEqual(body["soc"], 90)

    def test_parse_short_rs485_response_as_raw(self):
        payload = bytes.fromhex("0001")
        raw = append_crc(bytes([1, 0x03, len(payload)]) + payload)

        frame = parse_frame(raw)
        topic, message = mqtt_message_for_frame(frame, now_ms=123)
        body = json.loads(message)

        self.assertEqual(topic, "fengyan_daq_2026/data/node/1/rs485")
        self.assertEqual(body["payload_hex"], "0001")

    def test_parse_rs485_raw_response(self):
        payload = bytes.fromhex("010304000100020001")
        raw = append_crc(bytes([1, 0x41, len(payload)]) + payload)

        frame = parse_frame(raw)
        topic, message = mqtt_message_for_frame(frame, now_ms=123)
        body = json.loads(message)

        self.assertEqual(topic, "fengyan_daq_2026/data/node/1/rs485")
        self.assertEqual(body["payload_hex"], "010304000100020001")

    def test_extract_frames_skips_noise(self):
        payload = bytes.fromhex("08980078005A0000")
        raw = append_crc(bytes([1, 0x03, len(payload)]) + payload)

        frames, leftover = extract_frames(b"\xFF" + raw + b"\x01\x02")

        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].frame_type, 0x03)
        self.assertEqual(leftover, b"\x01\x02")


if __name__ == "__main__":
    unittest.main()
