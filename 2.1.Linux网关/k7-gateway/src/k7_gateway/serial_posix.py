"""Small POSIX serial helper without external dependencies."""

from __future__ import annotations

import os
import select
import termios
import time
from dataclasses import dataclass


BAUD_RATES = {
    1200: termios.B1200,
    2400: termios.B2400,
    4800: termios.B4800,
    9600: termios.B9600,
    19200: termios.B19200,
    38400: termios.B38400,
    57600: termios.B57600,
    115200: termios.B115200,
}


@dataclass
class SerialPort:
    device: str
    baud: int
    fd: int

    @classmethod
    def open(cls, device: str, baud: int) -> "SerialPort":
        if baud not in BAUD_RATES:
            raise ValueError(f"unsupported baud rate: {baud}")

        fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = (
            (attrs[2] & ~termios.PARENB & ~termios.CSTOPB & ~termios.CSIZE)
            | termios.CS8
            | termios.CLOCAL
            | termios.CREAD
        )
        attrs[3] = 0
        attrs[4] = BAUD_RATES[baud]
        attrs[5] = BAUD_RATES[baud]
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        termios.tcflush(fd, termios.TCIOFLUSH)
        return cls(device=device, baud=baud, fd=fd)

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def __enter__(self) -> "SerialPort":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def write(self, data: bytes) -> None:
        os.write(self.fd, data)

    def read_until_idle(self, timeout: float = 3.0, idle: float = 0.2) -> bytes:
        buf = bytearray()
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            readable, _, _ = select.select([self.fd], [], [], idle)
            if not readable:
                if buf:
                    break
                continue
            buf.extend(os.read(self.fd, 4096))
        return bytes(buf)

    def read_for(self, seconds: float) -> bytes:
        buf = bytearray()
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            readable, _, _ = select.select([self.fd], [], [], 0.2)
            if readable:
                buf.extend(os.read(self.fd, 4096))
        return bytes(buf)
