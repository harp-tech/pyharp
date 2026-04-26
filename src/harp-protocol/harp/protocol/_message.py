"""Harp message container."""

from __future__ import annotations

import struct
from typing import Any, Generic, TypeVar

from ._builder import build_message_frame
from ._checksum import validate as _validate_checksum
from ._message_type import MessageType
from ._payload import PayloadBase
from ._payload_type import PayloadType, decode_payload_type

P = TypeVar("P", bound=PayloadBase[Any])


class HarpParseError(Exception):
    pass


class HarpMessage:
    """A Harp message backed by its raw frame bytes.

    Build with the constructor or parse from wire bytes with ``HarpMessage.parse()``.
    """

    __slots__ = ("_frame",)

    def __init__(
        self,
        message_type: MessageType,
        address: int,
        payload_type: PayloadType,
        payload: bytes = b"",
        *,
        port: int = 0xFF,
        timestamp: float | None = None,
    ) -> None:
        self._frame: bytes = build_message_frame(
            message_type, address, payload_type, payload, port=port, timestamp=timestamp
        )

    @classmethod
    def parse(cls, data: bytes | bytearray | memoryview) -> "HarpMessage":
        """Parse and validate a complete Harp frame. Raises ``HarpParseError`` on failure."""
        raw = data if isinstance(data, bytes) else bytes(data)

        if len(raw) < 6:
            raise HarpParseError(f"Frame too short: {len(raw)} bytes (minimum 6)")

        if not _validate_checksum(raw):
            raise HarpParseError("Checksum mismatch")

        # Validate MessageType byte (bits 7,6,5,4,2 must be 0; bits 1:0 are type)
        b0 = raw[0]
        if b0 & 0b11110100:
            raise HarpParseError(f"Reserved bits set in MessageType byte: 0x{b0:02x}")
        if (b0 & 0x03) not in (1, 2, 3):
            raise HarpParseError(f"Invalid MessageType value in byte: 0x{b0:02x}")

        length = raw[1]
        if len(raw) != length + 2:
            raise HarpParseError(f"Length field {length} inconsistent with buffer size {len(raw)}")

        try:
            decode_payload_type(raw[4])
        except ValueError as exc:
            raise HarpParseError(str(exc)) from exc

        if bool(raw[4] & 0x10) and len(raw) < 5 + 6 + 1:
            raise HarpParseError("Frame too short to contain timestamp")

        obj = cls.__new__(cls)
        obj._frame = raw
        return obj

    # ------------------------------------------------------------------
    # Field accessors — direct bit reads into _frame, no copies
    # ------------------------------------------------------------------

    @property
    def message_type(self) -> MessageType:
        return MessageType(self._frame[0] & 0x03)

    @property
    def has_error(self) -> bool:
        return bool(self._frame[0] & 0x08)

    @property
    def address(self) -> int:
        return self._frame[2]

    @property
    def port(self) -> int:
        return self._frame[3]

    @property
    def payload_type(self) -> PayloadType:
        return decode_payload_type(self._frame[4]).payload_type

    @property
    def has_timestamp(self) -> bool:
        return bool(self._frame[4] & 0x10)

    @property
    def timestamp(self) -> float | None:
        if not self.has_timestamp:
            return None
        seconds, microseconds = struct.unpack_from("<IH", self._frame, 5)
        return seconds + microseconds * 32e-6

    @property
    def payload(self) -> memoryview:
        """Payload bytes, excluding timestamp and checksum."""
        offset = 11 if self.has_timestamp else 5
        return memoryview(self._frame)[offset:-1]

    def __repr__(self) -> str:
        return (
            f"HarpMessage(message_type={self.message_type!r}, address={self.address:#04x}, "
            f"payload_type={self.payload_type!r}, timestamp={self.timestamp!r})"
        )


class ParsedHarpMessage(HarpMessage, Generic[P]):
    """A ``HarpMessage`` with a typed parsed payload attached."""

    __slots__ = ("parsed",)

    def __init__(
        self,
        message_type: MessageType,
        address: int,
        payload_type: PayloadType,
        payload: bytes = b"",
        *,
        port: int = 0xFF,
        timestamp: float | None = None,
        parsed: P,
    ) -> None:
        super().__init__(
            message_type, address, payload_type, payload, port=port, timestamp=timestamp
        )
        self.parsed = parsed

    @classmethod
    def from_message(cls, msg: HarpMessage, parsed: P) -> "ParsedHarpMessage[P]":
        """Wrap a ``HarpMessage`` with a pre-parsed payload."""
        obj = cls.__new__(cls)
        obj._frame = msg._frame
        obj.parsed = parsed
        return obj


def parse(data: bytes | bytearray | memoryview) -> HarpMessage:
    """Parse a complete Harp message frame. Alias for ``HarpMessage.parse()``."""
    return HarpMessage.parse(data)
