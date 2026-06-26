"""K7 board baseline checks."""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
from dataclasses import dataclass

from .config import I2C7_DT_STATUS, K7_4G_DIAL_SCRIPT, K7_QUECTEL_CM, UART3_DT_STATUS


@dataclass(frozen=True)
class CheckItem:
    name: str
    ok: bool
    detail: str


def _read_dt_status(path: str) -> str:
    try:
        with open(path, "rb") as file:
            return file.read().replace(b"\x00", b"").decode("ascii", errors="replace")
    except FileNotFoundError:
        return "missing"
    except PermissionError:
        return "permission-denied"


def _run(command: list[str], timeout: float = 3.0) -> str:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return "command-not-found"
    except subprocess.TimeoutExpired:
        return "timeout"
    output = (result.stdout + result.stderr).strip()
    return output if output else f"exit={result.returncode}"


def run_checks() -> list[CheckItem]:
    tty_s = sorted(glob.glob("/dev/ttyS*"))
    tty_usb = sorted(glob.glob("/dev/ttyUSB*"))

    uart3_status = _read_dt_status(UART3_DT_STATUS)
    i2c7_status = _read_dt_status(I2C7_DT_STATUS)
    dmesg_uart = _run(["sh", "-c", "dmesg | grep -i -E 'ttyS3|2ad60000|uart3' | tail -n 5"])
    default_route = _run(["sh", "-c", "ip route show default || true"])

    return [
        CheckItem("/dev/ttyS3", os.path.exists("/dev/ttyS3"), ",".join(tty_s) or "no ttyS*"),
        CheckItem("uart3 device-tree", uart3_status == "okay", uart3_status),
        CheckItem("i2c7 device-tree", i2c7_status == "disabled", i2c7_status),
        CheckItem("dmesg uart3", "ttyS3" in dmesg_uart or "2ad60000" in dmesg_uart, dmesg_uart),
        CheckItem("/dev/ttyUSB2", os.path.exists("/dev/ttyUSB2"), ",".join(tty_usb) or "no ttyUSB*"),
        CheckItem("4G_dialing.sh", os.path.exists(K7_4G_DIAL_SCRIPT), K7_4G_DIAL_SCRIPT),
        CheckItem("quectel-CM", os.path.exists(K7_QUECTEL_CM), K7_QUECTEL_CM),
        CheckItem("ip command", shutil.which("ip") is not None, shutil.which("ip") or "missing"),
        CheckItem("default route", "default" in default_route, default_route),
    ]
