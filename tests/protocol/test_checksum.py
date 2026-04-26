import pytest
from harp.protocol._checksum import compute, validate


@pytest.mark.parametrize(
    "data, expected",
    [
        (
            bytes([0x01, 0x04, 0x00, 0xFF, 0x01, 0x00]),
            (0x01 + 0x04 + 0x00 + 0xFF + 0x01) & 0xFF,
        ),
        (bytes([0xFF] * 6), (0xFF * 5) & 0xFF),  # wraps
        (b"\xff", 0),  # single byte: sums nothing
    ],
)
def test_compute(data, expected):
    assert compute(data) == expected


@pytest.mark.parametrize(
    "frame, expected",
    [
        (None, True),  # None = auto-build a valid frame
        (bytes([0x02, 0x05, 0x00, 0xFF, 0x01, 0xAB, 0x00]), False),  # wrong checksum
        (b"\xff", False),  # too short
        (b"", False),  # empty
    ],
)
def test_validate(frame, expected):
    if frame is None:
        body = bytes([0x02, 0x05, 0x00, 0xFF, 0x01])
        frame = body + bytes([sum(body) & 0xFF])
    assert validate(frame) == expected
