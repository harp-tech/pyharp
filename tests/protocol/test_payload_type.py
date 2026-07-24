import pytest
from harp.protocol._payload_type import (
    PayloadType,
    decode_payload_type,
    encode_payload_type,
)


@pytest.mark.parametrize(
    "byte, expected_type, has_ts",
    [
        (0x01, PayloadType.U8, False),
        (0x02, PayloadType.U16, False),
        (0x04, PayloadType.U32, False),
        (0x08, PayloadType.U64, False),
        (0x81, PayloadType.S8, False),
        (0x82, PayloadType.S16, False),
        (0x84, PayloadType.S32, False),
        (0x88, PayloadType.S64, False),
        (0x44, PayloadType.Float, False),
        # With timestamp bit
        (0x11, PayloadType.U8, True),
        (0x12, PayloadType.U16, True),
        (0x14, PayloadType.U32, True),
        (0x18, PayloadType.U64, True),
        (0x91, PayloadType.S8, True),
        (0x92, PayloadType.S16, True),
        (0x94, PayloadType.S32, True),
        (0x98, PayloadType.S64, True),
        (0x54, PayloadType.Float, True),
    ],
)
def test_decode_valid(byte, expected_type, has_ts):
    info = decode_payload_type(byte)
    assert info.payload_type == expected_type
    assert info.has_timestamp == has_ts
    assert info.element_size == expected_type.numpy_dtype.itemsize


@pytest.mark.parametrize(
    "byte",
    [
        0x00,  # size nibble = 0
        0x03,  # size nibble = 3
        0x05,  # size nibble = 5
        0x20,  # reserved bit 5 set
        0xC4,  # IsFloat + IsSigned
        0x41,  # IsFloat + size=1 (8-bit float invalid)
        0x42,  # IsFloat + size=2
    ],
)
def test_decode_invalid(byte):
    with pytest.raises(ValueError):
        decode_payload_type(byte)


def test_encode_roundtrip():
    for pt in PayloadType:
        for has_ts in (False, True):
            b = encode_payload_type(pt, has_timestamp=has_ts)
            info = decode_payload_type(b)
            assert info.payload_type == pt
            assert info.has_timestamp == has_ts
