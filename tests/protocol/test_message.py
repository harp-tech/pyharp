import struct

import numpy as np
import pytest
from harp.protocol._message import HarpParseError, parse
from harp.protocol._message_type import MessageType
from harp.protocol._payload_type import PayloadType

from tests.fixtures import TIMESTAMP_1S, make_frame_from_raw


def test_parse_read_request():
    """Read request: no payload, no timestamp."""
    frame = make_frame_from_raw(0x01, address=8, port=0xFF, payload_type=0x04, payload=b"")
    msg = parse(frame)
    assert msg.message_type == MessageType.Read
    assert msg.has_error is False
    assert msg.address == 8
    assert msg.port == 0xFF
    assert msg.payload == b""
    assert msg.timestamp is None


def test_parse_write_u8_payload():
    frame = make_frame_from_raw(0x02, address=10, port=0xFF, payload_type=0x01, payload=b"\x05")
    msg = parse(frame)
    assert msg.message_type == MessageType.Write
    assert msg.payload == b"\x05"
    assert msg.payload_type == PayloadType.U8


def test_parse_with_timestamp():
    frame = make_frame_from_raw(
        0x03,
        address=32,
        port=0xFF,
        payload_type=0x11,  # U8 + HasTimestamp
        payload=b"\x7f",
        timestamp=TIMESTAMP_1S,
    )
    msg = parse(frame)
    assert msg.message_type == MessageType.Event
    assert msg.timestamp == pytest.approx(1.0)
    assert msg.payload == b"\x7f"


def test_parse_error_flag():
    frame = make_frame_from_raw(0x09, address=0, port=0xFF, payload_type=0x01, payload=b"\x00")
    msg = parse(frame)
    assert msg.has_error is True
    assert msg.message_type == MessageType.Read


def test_parse_u16_array():
    payload = struct.pack("<HHH", 100, 200, 300)
    frame = make_frame_from_raw(0x03, address=32, port=0xFF, payload_type=0x02, payload=payload)
    msg = parse(frame)
    arr = np.frombuffer(msg.payload, dtype=np.dtype("<u2"))
    assert list(arr) == [100, 200, 300]


def test_parse_bad_checksum():
    frame = bytearray(make_frame_from_raw(0x01, 8, 0xFF, 0x01, b""))
    frame[-1] ^= 0xFF  # corrupt checksum
    with pytest.raises(HarpParseError, match="[Cc]hecksum"):
        parse(bytes(frame))


def test_parse_too_short():
    with pytest.raises(HarpParseError):
        parse(b"\x01\x04\x00")  # truncated


def test_parse_bad_payload_type():
    frame = make_frame_from_raw(0x01, 8, 0xFF, 0x00, b"")  # size nibble=0 invalid
    # Recompute checksum after we force a bad payload_type byte.
    # make_frame uses the passed payload_type directly, but 0x00 has size=0 which
    # is invalid. The frame checksum is still correct; parse should reject the type.
    with pytest.raises(HarpParseError):
        parse(frame)


def test_parse_length_mismatch():
    # Build a frame then lie about the length byte.
    frame = bytearray(make_frame_from_raw(0x01, 8, 0xFF, 0x01, b""))
    frame[1] = 99  # wrong length
    # Recompute checksum to make it pass checksum check, still fails length check.
    frame[-1] = sum(frame[:-1]) & 0xFF
    with pytest.raises(HarpParseError):
        parse(bytes(frame))
        parse(bytes(frame))
