"""NetworkManager watchdog for K7 uplink failover."""

from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Sequence

from .network_status import CELLULAR_PREFIXES, WIFI_PREFIXES, default_route_interface


CELLULAR_PRIORITY = 100
WIFI_PRIORITY = 0
CELLULAR_METRIC = 100
WIFI_METRIC = 600


@dataclass(frozen=True)
class NmcliDevice:
    device: str
    type: str
    state: str
    connection: str


@dataclass(frozen=True)
class NmcliConnection:
    name: str
    type: str
    autoconnect: str


Runner = Callable[..., subprocess.CompletedProcess[str]]
Logger = Callable[[str], None]
InternetCheck = Callable[[], bool]


def split_nmcli_line(line: str) -> list[str]:
    """Split one nmcli -t line, honoring backslash escaped separators."""

    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line.rstrip("\n"):
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == ":":
            fields.append("".join(current))
            current = []
            continue
        current.append(char)
    fields.append("".join(current))
    return fields


def parse_devices(output: str) -> list[NmcliDevice]:
    devices: list[NmcliDevice] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = split_nmcli_line(line)
        while len(fields) < 4:
            fields.append("")
        devices.append(NmcliDevice(fields[0], fields[1], fields[2], fields[3]))
    return devices


def parse_connections(output: str) -> list[NmcliConnection]:
    connections: list[NmcliConnection] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = split_nmcli_line(line)
        while len(fields) < 3:
            fields.append("")
        connections.append(NmcliConnection(fields[0], fields[1], fields[2]))
    return connections


def parse_visible_ssids(output: str) -> set[str]:
    return {split_nmcli_line(line)[0] for line in output.splitlines() if line.strip()}


def is_cellular_device(device: NmcliDevice) -> bool:
    return device.type == "ethernet" and device.device.startswith(CELLULAR_PREFIXES)


def is_wifi_device(device: NmcliDevice) -> bool:
    return device.type == "wifi" or device.device.startswith(WIFI_PREFIXES)


def is_wifi_connection(connection: NmcliConnection) -> bool:
    return connection.type == "802-11-wireless"


def make_internet_check(host: str, port: int, timeout: float) -> InternetCheck:
    def check() -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    return check


class NetworkWatchdog:
    def __init__(
        self,
        *,
        runner: Runner = subprocess.run,
        internet_check: InternetCheck | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        logger: Logger = print,
        broker_host: str = "broker.emqx.io",
        broker_port: int = 1883,
        connect_timeout: float = 20.0,
        internet_timeout: float = 3.0,
    ) -> None:
        self.runner = runner
        self.internet_check = internet_check or make_internet_check(
            broker_host, broker_port, internet_timeout
        )
        self.sleeper = sleeper
        self.logger = logger
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.connect_timeout = connect_timeout

    def run_forever(self, interval: float) -> None:
        while True:
            self.run_once()
            self.sleeper(interval)

    def run_once(self) -> str:
        devices = self.list_devices()
        self.configure_priorities(devices)

        route_iface = default_route_interface()
        if route_iface and route_iface.startswith(CELLULAR_PREFIXES) and self.internet_check():
            self.logger(f"uplink ok: cellular via {route_iface}")
            return "cellular-ok"

        cellular_result = self.try_cellular(devices)
        if cellular_result == "cellular-ok":
            return cellular_result

        wifi_result = self.try_wifi()
        if wifi_result == "wifi-ok":
            return wifi_result

        route_iface = default_route_interface()
        if route_iface and self.internet_check():
            self.logger(f"uplink ok: existing route via {route_iface}")
            return "existing-ok"

        self.logger("uplink unavailable: cellular and saved visible WiFi are not ready")
        return "offline"

    def try_cellular(self, devices: Sequence[NmcliDevice]) -> str:
        cellular_devices = [device for device in devices if is_cellular_device(device)]
        if not cellular_devices:
            self.logger("cellular unavailable: no RG200U ethernet device")
            return "cellular-missing"

        for device in cellular_devices:
            if device.state == "connected":
                self.logger(f"cellular present: {device.device} already connected")
            else:
                self.logger(f"cellular connect attempt: {device.device}")
                self.nmcli(["device", "connect", device.device], timeout=self.connect_timeout)

            refreshed = self.list_devices()
            self.configure_priorities(refreshed)
            route_iface = default_route_interface()
            if route_iface and route_iface.startswith(CELLULAR_PREFIXES) and self.internet_check():
                self.logger(f"uplink ok: cellular via {route_iface}")
                return "cellular-ok"

        self.logger("cellular failed: no working cellular default route")
        return "cellular-failed"

    def try_wifi(self) -> str:
        wifi_devices = [device for device in self.list_devices() if is_wifi_device(device)]
        if not wifi_devices:
            self.logger("wifi unavailable: no WiFi device")
            return "wifi-missing"

        self.nmcli(["radio", "wifi", "on"], timeout=5.0)
        visible_ssids = self.visible_ssids()
        if not visible_ssids:
            self.logger("wifi skipped: no visible SSID")
            return "wifi-no-ssid"

        saved_wifi = [conn for conn in self.list_connections() if is_wifi_connection(conn)]
        for connection in saved_wifi:
            if connection.name not in visible_ssids:
                continue
            self.configure_connection(connection.name, WIFI_PRIORITY, WIFI_METRIC)
            self.logger(f"wifi connect attempt: saved profile '{connection.name}'")
            self.nmcli(["connection", "up", connection.name], timeout=self.connect_timeout)
            self.configure_priorities(self.list_devices())
            route_iface = default_route_interface()
            if route_iface and route_iface.startswith(WIFI_PREFIXES) and self.internet_check():
                self.logger(f"uplink ok: wifi via {route_iface}")
                return "wifi-ok"

        self.logger("wifi failed: no saved visible WiFi profile connected")
        return "wifi-failed"

    def configure_priorities(self, devices: Sequence[NmcliDevice]) -> None:
        for device in devices:
            if not device.connection or device.connection == "--":
                continue
            if is_cellular_device(device):
                self.configure_connection(device.connection, CELLULAR_PRIORITY, CELLULAR_METRIC)
            elif is_wifi_device(device):
                self.configure_connection(device.connection, WIFI_PRIORITY, WIFI_METRIC)

    def configure_connection(self, name: str, priority: int, metric: int) -> None:
        self.nmcli(
            [
                "connection",
                "modify",
                name,
                "connection.autoconnect",
                "yes",
                "connection.autoconnect-priority",
                str(priority),
                "ipv4.route-metric",
                str(metric),
                "ipv6.route-metric",
                str(metric),
            ],
            timeout=5.0,
        )

    def list_devices(self) -> list[NmcliDevice]:
        result = self.nmcli(
            ["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
            timeout=5.0,
        )
        return parse_devices(result.stdout)

    def list_connections(self) -> list[NmcliConnection]:
        result = self.nmcli(
            ["-t", "-f", "NAME,TYPE,AUTOCONNECT", "connection", "show"],
            timeout=5.0,
        )
        return parse_connections(result.stdout)

    def visible_ssids(self) -> set[str]:
        result = self.nmcli(
            ["-t", "-f", "SSID", "device", "wifi", "list"],
            timeout=10.0,
        )
        return parse_visible_ssids(result.stdout)

    def nmcli(self, args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
        try:
            result = self.runner(
                ["nmcli", *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self.logger(f"nmcli timeout: {' '.join(args)}")
            return subprocess.CompletedProcess(["nmcli", *args], 124, "", "timeout")
        except OSError as exc:
            self.logger(f"nmcli unavailable: {exc}")
            return subprocess.CompletedProcess(["nmcli", *args], 127, "", str(exc))

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            if detail:
                self.logger(f"nmcli failed: {' '.join(args)}: {detail}")
            else:
                self.logger(f"nmcli failed: {' '.join(args)}")
        return result


def run_network_watchdog(
    *,
    interval: float = 10.0,
    broker_host: str = "broker.emqx.io",
    broker_port: int = 1883,
    once: bool = False,
) -> int:
    watchdog = NetworkWatchdog(broker_host=broker_host, broker_port=broker_port)
    if once:
        result = watchdog.run_once()
        return 0 if result.endswith("-ok") else 1
    watchdog.run_forever(interval)
    return 0
