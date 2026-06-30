"""Network transport detection for gateway status reporting."""

from __future__ import annotations

import os
import re
import select
import subprocess
import time
from pathlib import Path

try:
    import termios
except ImportError:  # pragma: no cover - Windows test host
    termios = None  # type: ignore[assignment]


Transport = str

WIFI_PREFIXES = ("wlan", "wlp")
CELLULAR_PREFIXES = ("wwan", "usb", "enx")
CELLULAR_FALLBACK: Transport = "4g"


def default_route_interface(route_path: str = "/proc/net/route") -> str | None:
    """Return the interface used by the lowest-metric IPv4 default route."""

    try:
        lines = Path(route_path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    best: tuple[int, str] | None = None
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 8:
            continue
        iface, destination, _gateway, flags, *_rest = fields[:7]
        metric = fields[6]
        if destination != "00000000":
            continue
        try:
            route_flags = int(flags, 16)
            route_metric = int(metric)
        except ValueError:
            continue
        if (route_flags & 0x2) == 0:
            continue
        if best is None or route_metric < best[0]:
            best = (route_metric, iface)
    return None if best is None else best[1]


def transport_from_cops_response(response: str) -> Transport | None:
    """Map Quectel/3GPP AT+COPS? access technology to 4g/5g."""

    match = re.search(r"\+COPS:\s*\d+\s*,\s*\d+\s*,\s*\"[^\"]*\"\s*,\s*(\d+)", response)
    if not match:
        return None
    act = int(match.group(1))
    if act in {10, 11, 12, 13}:
        return "5g"
    if act in {7, 8, 9}:
        return "4g"
    return None


def _configure_serial(fd: int) -> None:
    if termios is None:
        raise OSError("termios is unavailable on this platform")
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = termios.B115200
    attrs[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def _read_serial(fd: int, timeout: float) -> bytes:
    output = bytearray()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], 0.15)
        if not ready:
            continue
        try:
            output.extend(os.read(fd, 4096))
        except BlockingIOError:
            continue
    return bytes(output)


def query_at_command(port: str, command: str, timeout: float = 1.2) -> str | None:
    """Send one AT command to a serial port and return the raw response."""

    try:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        _configure_serial(fd)
        try:
            os.read(fd, 4096)
        except BlockingIOError:
            pass
        os.write(fd, (command + "\r").encode("ascii"))
        return _read_serial(fd, timeout).decode("ascii", "replace")
    except OSError:
        return None
    finally:
        os.close(fd)


def query_cellular_transport() -> Transport | None:
    """Detect current cellular radio generation through ModemManager or AT ports."""

    quectel_log_transport = _query_cellular_transport_with_quectel_log()
    if quectel_log_transport:
        return quectel_log_transport

    mmcli_transport = _query_cellular_transport_with_mmcli()
    if mmcli_transport:
        return mmcli_transport

    ports = sorted(Path("/dev").glob("ttyUSB*"))
    ports = sorted(ports, key=lambda item: 0 if item.name == "ttyUSB2" else 1)
    for port in ports:
        at = query_at_command(str(port), "AT", timeout=0.5)
        if not at or "OK" not in at:
            continue
        cops = query_at_command(str(port), "AT+COPS?", timeout=1.2)
        if not cops:
            continue
        transport = transport_from_cops_response(cops)
        if transport:
            return transport
    return None


def _query_cellular_transport_with_quectel_log(log_path: str = "/tmp/4G.log") -> Transport | None:
    """Read quectel-CM log instead of probing modem AT ports in the hot path."""

    try:
        raw = Path(log_path).read_bytes()[-65536:]
    except OSError:
        return None
    text = raw.decode("utf-8", "replace")
    matches = list(re.finditer(r"\+COPS:\s*\d+\s*,\s*\d+\s*,\s*\"[^\"]*\"\s*,\s*\d+", text))
    for match in reversed(matches):
        transport = transport_from_cops_response(match.group(0))
        if transport:
            return transport
    return None


def _query_cellular_transport_with_mmcli() -> Transport | None:
    try:
        listing = subprocess.run(
            ["mmcli", "-L"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"/Modem/(\d+)", listing.stdout)
    if not match:
        return None
    modem = match.group(1)
    try:
        result = subprocess.run(
            ["mmcli", "-m", modem, "--command=AT+COPS?"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return transport_from_cops_response(result.stdout + result.stderr)


def detect_transport() -> Transport:
    """Detect current active uplink as wifi/4g/5g."""

    iface = default_route_interface()
    if iface is None:
        return "wifi"
    if iface.startswith(WIFI_PREFIXES):
        return "wifi"
    if iface.startswith(CELLULAR_PREFIXES):
        return query_cellular_transport() or CELLULAR_FALLBACK
    return "wifi"


def resolve_transport(configured: str) -> Transport:
    if configured == "auto":
        return detect_transport()
    return configured
