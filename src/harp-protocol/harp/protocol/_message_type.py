from enum import IntEnum


class MessageType(IntEnum):
    Read = 1
    Write = 2
    Event = 3


# Bits 7,6,5,4,2 must be 0; bit 3 is error; bits 1:0 are type.
_RESERVED_MASK = 0b11110100
_VALID_TYPES = frozenset(t.value for t in MessageType)


def from_byte(b: int) -> tuple["MessageType", bool]:
    """Decode a MessageType byte into ``(MessageType, has_error)``. Raises ``ValueError`` on invalid input."""
    if b & _RESERVED_MASK:
        raise ValueError(f"Reserved bits set in MessageType byte: 0x{b:02x}")
    type_bits = b & 0x03
    if type_bits not in _VALID_TYPES:
        raise ValueError(f"Invalid MessageType value {type_bits} in byte: 0x{b:02x}")
    return MessageType(type_bits), bool(b & 0x08)


def to_byte(message_type: MessageType, has_error: bool = False) -> int:
    """Encode MessageType + error flag to a single byte."""
    return message_type.value | (0x08 if has_error else 0)
