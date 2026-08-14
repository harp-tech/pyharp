import enum

import numpy as np
import pytest
from harp.data import payload_to_dataframe
from harp.protocol import AnonymousPayload, Column, GroupMask
from harp.protocol._payload import PayloadBase, Field, _IdentityConverter


class SimplePayload(PayloadBase):
    x = Field(converter=_IdentityConverter("<i2"), offset=0)
    y = Field(converter=_IdentityConverter("<u1"), offset=2)


class BitPackedPayload(PayloadBase):
    packed = Field(converter=_IdentityConverter("u1"))

    def payload_as_columns(
        self, *, decode_enums: bool = True, demux_bit_masks: bool = False
    ) -> list[Column]:
        return [
            Column("flag_a", (self.payload_array["packed"] & 0x01).astype(bool)),
            Column("flag_b", ((self.payload_array["packed"] >> 1) & 0x01).astype(bool)),
        ]


def _make_simple_bytes(n: int) -> bytes:
    arr = np.zeros(n, dtype=SimplePayload.payload_dtype)
    arr["x"] = np.arange(n, dtype=np.int16) * -1
    arr["y"] = np.arange(n, dtype=np.uint8)
    return arr.tobytes()


def test_from_buffer_shape():
    data = _make_simple_bytes(5)
    p = SimplePayload.payload_from_buffer(data)
    assert len(p) == 5


def test_from_buffer_values():
    data = _make_simple_bytes(3)
    p = SimplePayload.payload_from_buffer(data)
    np.testing.assert_array_equal(p.x, [0, -1, -2])
    np.testing.assert_array_equal(p.y, [0, 1, 2])


def test_to_dataframe_columns():
    p = SimplePayload.payload_from_buffer(_make_simple_bytes(3))
    df = payload_to_dataframe(p)
    assert list(df.columns) == ["x", "y"]
    assert len(df) == 3


def test_to_dataframe_override():
    arr = np.array(
        [(0b00000011,), (0b00000001,), (0b00000010,)], dtype=BitPackedPayload.payload_dtype
    )
    p = BitPackedPayload.payload_from_buffer(arr.tobytes())
    df = payload_to_dataframe(p)
    assert list(df.columns) == ["flag_a", "flag_b"]
    assert list(df["flag_a"]) == [True, True, False]
    assert list(df["flag_b"]) == [True, False, True]


def test_from_buffer_zero_copy():
    data = _make_simple_bytes(4)
    p = SimplePayload.payload_from_buffer(data)
    # np.frombuffer returns a read-only view, so writes should raise
    with pytest.raises((ValueError, TypeError)):
        p.payload_array["x"][0] = 999


def test_payload_property():
    p = SimplePayload.payload_from_buffer(_make_simple_bytes(2))
    assert p.payload_array.dtype == SimplePayload.payload_dtype


class _SparseMode(enum.IntEnum):
    Low = 0
    High = 2  # gap at code 1; largest member is 2


class _SparseModePayload(AnonymousPayload[np.uint8]):
    # Whole-byte GroupMask over a sparse enum: raw can be 0..255, well past the
    # largest member, so decode must not IndexError on undefined codes.
    __value__ = GroupMask(enum=_SparseMode, mask=0xFF)


def test_groupmask_undefined_code_preserves_raw():
    # Codes: defined (0->Low, 2->High), an in-range gap (1), and out-of-range (90, 255).
    # Every undefined code is preserved as its raw int, like the unchecked cast in C#,
    batch = _SparseModePayload.payload_from_buffer(
        np.array([0, 2, 1, 90, 255], dtype=np.uint8).tobytes()
    )
    assert list(payload_to_dataframe(batch)["value"]) == ["Low", "High", 1, 90, 255]


def test_groupmask_scalar_matches_batch_for_undefined():
    # Scalar decode is permissive the same way
    defined = _SparseModePayload.payload_from_buffer(np.array([2], dtype=np.uint8).tobytes())
    assert defined.__value__ is _SparseMode.High
    undefined = _SparseModePayload.payload_from_buffer(np.array([90], dtype=np.uint8).tobytes())
    assert undefined.__value__ == 90
    assert not isinstance(undefined.__value__, _SparseMode)
