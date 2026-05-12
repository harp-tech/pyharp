"""High-level Harp device API."""

from typing import Any, TypeVar

from harp.protocol._message import ParsedHarpMessage
from harp.protocol._register import RegisterBase

from ._serial import SerialDevice

P = TypeVar("P")


class Device:
    def __init__(self, port: str, baudrate: int = SerialDevice.DEFAULT_BAUDRATE) -> None:
        self._dev = SerialDevice(port, baudrate)

    def read(self, register: type[RegisterBase[P]]) -> ParsedHarpMessage[P]:
        # Note: ty can't correctly infer the return type, and this is a known issue:
        # https://github.com/astral-sh/ty/issues/623
        return self._dev.read_register(register)

    def write(self, register: type[RegisterBase[P]], value: Any) -> ParsedHarpMessage[P]:
        return self._dev.write_register(register, value)

    def close(self) -> None:
        self._dev.close()

    def __enter__(self) -> "Device":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
