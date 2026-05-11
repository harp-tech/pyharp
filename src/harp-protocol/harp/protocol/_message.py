"""Harp message container."""

import struct
from typing import Any, Generic, TypeVar, cast

from ._builder import build_message_frame
from ._checksum import validate as _validate_checksum
from ._message_type import MessageType, _message_type_from_byte_safe
from ._payload import PayloadBase
from ._payload_type import PayloadType, decode_payload_type

P = TypeVar("P", bound=PayloadBase[Any])


class HarpParseError(Exception):
    pass


class HarpMessage:
    """A Harp message backed by its raw frame bytes.

    Build with the constructor or parse from wire bytes with ``HarpMessage.parse()``.
    """

    __slots__ = ("_bytes",)

    def __init__(
        self,
        message_type: MessageType,
        address: int,
        payload_type: PayloadType,
        payload: "bytes" = b"",
        *,
        port: int = 0xFF,
        timestamp: float | None = None,
    ) -> None:
        self._bytes: "bytes" = build_message_frame(
            message_type, address, payload_type, payload, port=port, timestamp=timestamp
        )

    @classmethod
    def parse(cls, data: bytes | bytearray | memoryview) -> "HarpMessage":
        """Parse and validate a complete Harp Message from a byte sequence. Raises ``HarpParseError`` on failure."""
        raw = data if isinstance(data, bytes) else bytes(data)

        if len(raw) < 6:
            raise HarpParseError(f"Frame too short: {len(raw)} bytes (minimum 6)")

        if not _validate_checksum(raw):
            raise HarpParseError("Checksum mismatch")

        # Validate MessageType byte (bits 7,6,5,4,2 must be 0; bits 1:0 are type)
        b0 = raw[0]
        if _message_type_from_byte_safe(b0) is None:
            raise HarpParseError(f"Invalid MessageType byte: 0x{b0:02x}")

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
        obj._bytes = raw
        return obj

    @property
    def message_type(self) -> MessageType:
        """Return the MessageType of this message."""
        return MessageType(self._bytes[0] & 0x03)

    @property
    def has_error(self) -> bool:
        """Return True if the error flag is set in this message."""
        return bool(self._bytes[0] & 0x08)

    @property
    def address(self) -> int:
        """Return the address byte of this message."""
        return self._bytes[2]

    @property
    def port(self) -> int:
        """Return the port byte of this message."""
        return self._bytes[3]

    @property
    def payload_type(self) -> PayloadType:
        """Return the PayloadType of this message."""
        return decode_payload_type(self._bytes[4]).payload_type

    @property
    def has_timestamp(self) -> bool:
        """Return True if the timestamp flag is set in this message."""
        return bool(self._bytes[4] & 0x10)

    @property
    def timestamp(self) -> float | None:
        """Return the timestamp of this message, or None if not present."""
        if not self.has_timestamp:
            return None
        seconds, microseconds = struct.unpack_from("<IH", self._bytes, 5)
        return cast(int, seconds) + cast(int, microseconds) * 32e-6

    @property
    def payload(self) -> memoryview:
        """Payload bytes, excluding timestamp and checksum."""
        offset = 11 if self.has_timestamp else 5
        return memoryview(self._bytes)[offset:-1]

    @property
    def bytes(self) -> bytes:
        """The complete raw message frame, including checksum."""
        return self._bytes

    def __str__(self) -> str:
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
        obj._bytes = msg.bytes
        obj.parsed = parsed
        return obj
