import numpy as np
import pandas as pd
import pytest
from harp.protocol._payload import PayloadBase, _Field, _IdentityConverter


class SimplePayload(PayloadBase):
    x = _Field(_IdentityConverter("<i2"))
    y = _Field(_IdentityConverter("<u1"))


class BitPackedPayload(PayloadBase):
    packed = _Field(_IdentityConverter("u1"))

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "flag_a": (self.raw_payload["packed"] & 0x01).astype(bool),
                "flag_b": ((self.raw_payload["packed"] >> 1) & 0x01).astype(bool),
            }
        )


def _make_simple_bytes(n: int) -> bytes:
    arr = np.zeros(n, dtype=SimplePayload.dtype)
    arr["x"] = np.arange(n, dtype=np.int16) * -1
    arr["y"] = np.arange(n, dtype=np.uint8)
    return arr.tobytes()


def test_from_buffer_shape():
    data = _make_simple_bytes(5)
    p = SimplePayload.from_buffer(data)
    assert len(p) == 5


def test_from_buffer_values():
    data = _make_simple_bytes(3)
    p = SimplePayload.from_buffer(data)
    np.testing.assert_array_equal(p.x, [0, -1, -2])
    np.testing.assert_array_equal(p.y, [0, 1, 2])


def test_to_dataframe_columns():
    p = SimplePayload.from_buffer(_make_simple_bytes(3))
    df = p.to_dataframe()
    assert list(df.columns) == ["x", "y"]
    assert len(df) == 3


def test_to_dataframe_override():
    arr = np.array([(0b00000011,), (0b00000001,), (0b00000010,)], dtype=BitPackedPayload.dtype)
    p = BitPackedPayload.from_buffer(arr.tobytes())
    df = p.to_dataframe()
    assert list(df.columns) == ["flag_a", "flag_b"]
    assert list(df["flag_a"]) == [True, True, False]
    assert list(df["flag_b"]) == [True, False, True]


def test_from_buffer_zero_copy():
    data = _make_simple_bytes(4)
    p = SimplePayload.from_buffer(data)
    # np.frombuffer returns a read-only view — writes should raise
    with pytest.raises((ValueError, TypeError)):
        p.raw_payload["x"][0] = 999


def test_payload_property():
    p = SimplePayload.from_buffer(_make_simple_bytes(2))
    assert p.raw_payload.dtype == SimplePayload.dtype
