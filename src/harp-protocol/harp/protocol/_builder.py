"""Utilities for building outgoing Harp message frames."""

import struct

from ._constants import _DEFAULT_PORT, _TICK_PERIOD_S
from ._message_type import MessageType
from ._message_type import message_type_to_byte as _msg_type_byte
from ._payload_type import PayloadType, encode_payload_type


def build_message_frame(
    message_type: MessageType,
    address: int,
    payload_type: PayloadType,
    payload: bytes = b"",
    *,
    port: int = _DEFAULT_PORT,
    timestamp: float | None = None,
) -> bytes:
    """Build and return a complete Harp wire frame as bytes."""
    if timestamp is not None:
        seconds = int(timestamp)
        microseconds = round((timestamp - seconds) / _TICK_PERIOD_S)
        ts_bytes = struct.pack("<IH", seconds, microseconds)
    else:
        ts_bytes = b""
    pt_byte = encode_payload_type(payload_type, has_timestamp=timestamp is not None)
    body = bytes([address, port, pt_byte]) + ts_bytes + payload
    length = len(body) + 1  # +1 for checksum
    header = bytes([_msg_type_byte(message_type), length])
    frame = header + body
    checksum = sum(frame) & 0xFF
    return frame + bytes([checksum])
