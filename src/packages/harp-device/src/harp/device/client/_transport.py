"""Byte transport abstraction for Harp devices."""

from typing import Protocol, runtime_checkable


class TransportError(Exception):
    """Raised by a transport when the underlying byte channel fails."""


@runtime_checkable
class ITransport(Protocol):
    """Byte channel a :class:`~harp.device.client.Device` drives.

    Owns no protocol logic. Failures are reported as :class:`TransportError`.
    """

    def open(self) -> None: ...

    def write(self, data: bytes) -> None: ...

    def read(self) -> bytes:
        """Return available bytes, or ``b''`` on idle/timeout."""
        ...

    def close(self) -> None: ...
