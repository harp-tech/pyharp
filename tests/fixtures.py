

TIMESTAMP_1S: bytes = b"\x01\x00\x00\x00\x00\x00"


def make_frame_from_raw(
    msg_type_byte: int,
    address: int,
    port: int,
    payload_type: int,
    payload: bytes,
    *,
    timestamp: bytes | None = None,
) -> bytes:
    """Build a raw Harp frame from individual byte-level fields (for tests)."""
    ts = timestamp if timestamp is not None else b""
    pt_byte = payload_type | (0x10 if ts else 0)
    body = bytes([address, port, pt_byte]) + ts + payload
    length = len(body) + 1  # +1 for checksum
    frame = bytes([msg_type_byte, length]) + body
    checksum = sum(frame) & 0xFF
    return frame + bytes([checksum])
