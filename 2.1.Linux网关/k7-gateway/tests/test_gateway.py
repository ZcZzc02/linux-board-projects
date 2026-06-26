import json
import unittest

from k7_gateway.gateway import records_from_chunk
from k7_gateway.lora_protocol import append_crc


class GatewayRuntimeTest(unittest.TestCase):
    def test_records_from_chunk_returns_jsonl_ready_records(self):
        payload = bytes.fromhex("00010002000300040005000600070008")
        raw = append_crc(bytes([1, 0x01, len(payload)]) + payload)

        records, leftover = records_from_chunk(b"", b"\x55" + raw, node_count=1)

        self.assertEqual(leftover, b"")
        self.assertEqual(len(records), 1)
        line = records[0].to_json_line()
        body = json.loads(line)

        self.assertEqual(body["topic"], "fengyan_daq_2026/data/node/1/ad7606")
        self.assertEqual(body["payload"]["channels_raw"][:2], [1, 2])

    def test_records_from_chunk_keeps_incomplete_frame(self):
        payload = bytes.fromhex("00010002000300040005000600070008")
        raw = append_crc(bytes([1, 0x01, len(payload)]) + payload)

        records, leftover = records_from_chunk(b"", raw[:4], node_count=1)

        self.assertEqual(records, [])
        self.assertEqual(leftover, raw[:4])


if __name__ == "__main__":
    unittest.main()
