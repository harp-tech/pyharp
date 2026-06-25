from typing import ClassVar

import serial

from ._device import Device


class SerialDevice(Device):
    """A :class:`Device` whose transport is a serial port."""

    DEFAULT_BAUDRATE: ClassVar[int] = 1_000_000

    def __init__(
        self, port: str, baudrate: int = DEFAULT_BAUDRATE, *, raise_on_error: bool = True
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None
        super().__init__(raise_on_error=raise_on_error)

    def _open(self) -> None:
        self._serial = serial.Serial(self._port, self._baudrate, timeout=0.1)
        self._serial.dtr = True

    def _write(self, data: bytes) -> None:
        assert self._serial is not None
        self._serial.write(data)

    def _read(self) -> bytes:
        assert self._serial is not None
        try:
            waiting = self._serial.in_waiting
            return self._serial.read(waiting if waiting > 0 else 1)
        except serial.SerialException:
            if self._running:
                raise
            return b""

    def _close(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.dtr = False
        except Exception:
            pass
        self._serial.close()
