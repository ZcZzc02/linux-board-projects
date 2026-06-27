import unittest

from k7_gateway.mqtt_simple import (
    build_puback_packet,
    build_subscribe_packet,
    build_connect_packet,
    build_publish_packet,
    encode_remaining_length,
    encode_utf8,
)


class MqttSimpleTest(unittest.TestCase):
    def test_encode_remaining_length(self):
        self.assertEqual(encode_remaining_length(0), b"\x00")
        self.assertEqual(encode_remaining_length(127), b"\x7f")
        self.assertEqual(encode_remaining_length(128), b"\x80\x01")
        self.assertEqual(encode_remaining_length(321), b"\xc1\x02")

    def test_encode_utf8(self):
        self.assertEqual(encode_utf8("MQTT"), b"\x00\x04MQTT")

    def test_build_connect_packet(self):
        packet = build_connect_packet(client_id="client-a", keepalive=60)

        self.assertEqual(packet[0], 0x10)
        self.assertIn(b"\x00\x04MQTT\x04\x02\x00\x3c", packet)
        self.assertTrue(packet.endswith(b"\x00\x08client-a"))

    def test_build_publish_packet(self):
        packet = build_publish_packet("topic/a", '{"ok":1}')

        self.assertEqual(packet[0], 0x30)
        self.assertIn(b"\x00\x07topic/a", packet)
        self.assertTrue(packet.endswith(b'{"ok":1}'))

    def test_build_subscribe_packet(self):
        packet = build_subscribe_packet("topic/+", packet_id=7, qos=1)

        self.assertEqual(packet[0], 0x82)
        self.assertIn(b"\x00\x07\x00\x07topic/+\x01", packet)

    def test_build_puback_packet(self):
        self.assertEqual(build_puback_packet(7), b"\x40\x02\x00\x07")


if __name__ == "__main__":
    unittest.main()
