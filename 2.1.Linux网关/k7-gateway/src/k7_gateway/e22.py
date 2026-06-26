"""EBYTE E22 helper commands."""

from __future__ import annotations

from dataclasses import dataclass

from .config import E22_EXPECTED_CONFIG, E22_READ_CONFIG_CMD


@dataclass(frozen=True)
class E22ConfigReadResult:
    tx: bytes
    rx: bytes
    expected: bytes = E22_EXPECTED_CONFIG

    @property
    def ok(self) -> bool:
        return self.rx == self.expected

    def as_lines(self) -> list[str]:
        return [
            f"TX_HEX={self.tx.hex()}",
            f"RX_LEN={len(self.rx)}",
            f"RX_HEX={self.rx.hex()}",
            f"EXPECTED_HEX={self.expected.hex()}",
            f"OK={str(self.ok).lower()}",
        ]


def read_config(device: str, baud: int = 9600, timeout: float = 3.0) -> E22ConfigReadResult:
    from .serial_posix import SerialPort

    with SerialPort.open(device, baud) as port:
        port.write(E22_READ_CONFIG_CMD)
        rx = port.read_until_idle(timeout=timeout)
    return E22ConfigReadResult(tx=E22_READ_CONFIG_CMD, rx=rx)
