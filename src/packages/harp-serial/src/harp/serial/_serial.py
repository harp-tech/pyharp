"""Serial transport and factory for Harp devices."""

from typing import TypeVar

import serial

from harp.device.client import Device, TransportError

D = TypeVar("D", bound=Device)

DEFAULT_BAUDRATE: int = 1_000_000


class SerialTransport:
    """A serial-port :class:`~harp.device.client.ITransport` (structural conformance)."""

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE) -> None:
        self._port = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None

    def open(self) -> None:
        try:
            self._serial = serial.Serial(self._port, self._baudrate, timeout=0.1)
            self._serial.dtr = True
        except serial.SerialException as exc:
            raise TransportError(f"Failed to open serial port {self._port!r}: {exc}") from exc

    def write(self, data: bytes) -> None:
        assert self._serial is not None
        try:
            self._serial.write(data)
        except serial.SerialException as exc:
            raise TransportError(str(exc)) from exc

    def read(self) -> bytes:
        assert self._serial is not None
        try:
            waiting = self._serial.in_waiting
            return self._serial.read(waiting if waiting > 0 else 1)
        except serial.SerialException as exc:
            raise TransportError(str(exc)) from exc

    def close(self) -> None:
        if self._serial is None:
            return
        try:
            self._serial.dtr = False
        except Exception:
            pass
        self._serial.close()


def open_serial_device(
    device: type[D],
    *,
    port: str,
    baudrate: int = DEFAULT_BAUDRATE,
    raise_on_error: bool = True,
) -> D:
    """Build ``device`` over a serial transport and open it.

    Like the builtin :func:`open`, the returned device is already connected;
    use it directly or in a ``with`` block for guaranteed close::

        with open_serial_device(behavior.Device, port="COM3") as dev:
            dev.read(behavior.WhoAmI)
    """
    transport = SerialTransport(port, baudrate)
    return device(transport, raise_on_error=raise_on_error).open()
