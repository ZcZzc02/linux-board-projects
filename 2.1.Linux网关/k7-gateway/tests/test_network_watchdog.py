import subprocess
import unittest
from unittest.mock import patch

from k7_gateway import network_watchdog as nw


def completed(stdout=""):
    return subprocess.CompletedProcess(["nmcli"], 0, stdout, "")


class FakeRunner:
    def __init__(self, outputs):
        self.outputs = outputs
        self.commands = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        key = tuple(cmd[1:])
        return completed(self.outputs.get(key, ""))


class NetworkWatchdogTest(unittest.TestCase):
    def test_split_nmcli_line_handles_escaped_colons(self):
        self.assertEqual(
            nw.split_nmcli_line(r"wlan0:wifi:connected:Lab\:WiFi"),
            ["wlan0", "wifi", "connected", "Lab:WiFi"],
        )

    def test_parse_devices_and_connections(self):
        devices = nw.parse_devices("enx1:ethernet:connected:Wired connection 4\nwlan0:wifi:disconnected:\n")
        self.assertEqual(devices[0].device, "enx1")
        self.assertTrue(nw.is_cellular_device(devices[0]))
        self.assertTrue(nw.is_wifi_device(devices[1]))

        connections = nw.parse_connections("吃不饱:802-11-wireless:yes\n")
        self.assertTrue(nw.is_wifi_connection(connections[0]))

    def test_cellular_connected_is_preferred(self):
        runner = FakeRunner(
            {
                ("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"): (
                    "enxf2:ethernet:connected:Wired connection 4\n"
                    "wlan0:wifi:disconnected:\n"
                )
            }
        )
        watchdog = nw.NetworkWatchdog(runner=runner, internet_check=lambda: True, logger=lambda msg: None)

        with patch.object(nw, "default_route_interface", return_value="enxf2"):
            self.assertEqual(watchdog.run_once(), "cellular-ok")

        joined_commands = [" ".join(command) for command in runner.commands]
        self.assertTrue(
            any(
                "connection modify Wired connection 4" in command
                and "ipv4.route-metric 100" in command
                for command in joined_commands
            )
        )

    def test_wifi_fallback_uses_only_saved_visible_profile(self):
        runner = FakeRunner(
            {
                ("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"): (
                    "wlan0:wifi:disconnected:\n"
                ),
                ("-t", "-f", "SSID", "device", "wifi", "list"): "吃不饱\n",
                ("-t", "-f", "NAME,TYPE,AUTOCONNECT", "connection", "show"): (
                    "吃不饱:802-11-wireless:yes\n"
                    "Other:802-11-wireless:yes\n"
                ),
            }
        )
        watchdog = nw.NetworkWatchdog(runner=runner, internet_check=lambda: True, logger=lambda msg: None)

        with patch.object(nw, "default_route_interface", side_effect=[None, "wlan0"]):
            self.assertEqual(watchdog.run_once(), "wifi-ok")

        joined_commands = [" ".join(command) for command in runner.commands]
        self.assertTrue(any(command.endswith("connection up 吃不饱") for command in joined_commands))
        self.assertFalse(any(command.endswith("connection up Other") for command in joined_commands))


if __name__ == "__main__":
    unittest.main()
