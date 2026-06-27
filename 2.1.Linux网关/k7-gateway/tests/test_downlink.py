import unittest

from k7_gateway.downlink import DownlinkCommandError, frame_from_command
from k7_gateway.lora_protocol import append_crc


class DownlinkCommandTest(unittest.TestCase):
    def test_rs485_raw_command(self):
        frame = frame_from_command(
            "fengyan_daq_2026/cmd/node/1",
            b'{"cmd":"rs485_raw","params":{"hex":"01 03 00 00 00 04 44 09"}}',
        )

        self.assertEqual(
            frame.raw,
            append_crc(bytes.fromhex("01 41 08 01 03 00 00 00 04 44 09")),
        )

    def test_rs485_read_command(self):
        frame = frame_from_command(
            "fengyan_daq_2026/cmd/node/1",
            b'{"cmd":"rs485_read","params":{"reg":1024,"count":1}}',
        )

        self.assertEqual(frame.raw, append_crc(bytes.fromhex("01 03 04 00 00 01")))

    def test_rs485_write_command(self):
        frame = frame_from_command(
            "fengyan_daq_2026/cmd/node/1",
            b'{"cmd":"rs485_write","params":{"reg":1024,"data":"0002"}}',
        )

        self.assertEqual(frame.raw, append_crc(bytes.fromhex("01 06 04 00 00 02")))

    def test_can_relay_command(self):
        frame = frame_from_command(
            "fengyan_daq_2026/cmd/node/1",
            b'{"cmd":"relay","params":{"bus":"can","can_id":"0x123","data":"01 02 03","dlc":3}}',
        )

        self.assertEqual(frame.raw, append_crc(bytes.fromhex("01 42 06 01 23 03 01 02 03")))

    def test_unsupported_command_fails_closed(self):
        with self.assertRaises(DownlinkCommandError):
            frame_from_command(
                "fengyan_daq_2026/cmd/node/1",
                b'{"cmd":"reset","params":{}}',
            )


if __name__ == "__main__":
    unittest.main()
