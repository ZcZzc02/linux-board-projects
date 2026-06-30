import os
import tempfile
import textwrap
import unittest

from k7_gateway.network_status import (
    _query_cellular_transport_with_quectel_log,
    default_route_interface,
    resolve_transport,
    transport_from_cops_response,
)


class NetworkStatusTest(unittest.TestCase):
    def test_default_route_interface_uses_lowest_metric(self):
        content = textwrap.dedent(
            """\
            Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT
            wlan0 00000000 0100A8C0 0003 0 0 600 00000000 0 0 0
            enx1 00000000 01097764 0003 0 0 100 00000000 0 0 0
            """
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
            fh.write(content)
            path = fh.name

        try:
            self.assertEqual(default_route_interface(path), "enx1")
        finally:
            os.unlink(path)

    def test_transport_from_cops_response_maps_lte_to_4g(self):
        self.assertEqual(
            transport_from_cops_response('\r\n+COPS: 0,2,"46011",7\r\n\r\nOK\r\n'),
            "4g",
        )

    def test_transport_from_cops_response_maps_nr_to_5g(self):
        self.assertEqual(
            transport_from_cops_response('\r\n+COPS: 0,2,"46011",11\r\n\r\nOK\r\n'),
            "5g",
        )

    def test_resolve_transport_keeps_manual_value(self):
        self.assertEqual(resolve_transport("wifi"), "wifi")

    def test_query_cellular_transport_reads_latest_quectel_cops_log(self):
        content = textwrap.dedent(
            """\
            [06-30_10:39:30:506] AT< +COPS: 0,2,"46011",7
            [06-30_10:39:33:207] AT< +COPS: 0,2,"46011",11
            """
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
            fh.write(content)
            path = fh.name

        try:
            self.assertEqual(_query_cellular_transport_with_quectel_log(path), "5g")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
