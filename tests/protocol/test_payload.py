from typing import ClassVar

import numpy as np
import pandas as pd
import pytest
from harp.protocol._payload import PayloadBase
from numpy.typing import NDArray


class SimplePayload(PayloadBase):
    _dtype: ClassVar = np.dtype([("x", "<i2"), ("y", "<u1")])

    @property
    def x(self) -> NDArray[np.int16]:
        return self._arr["x"]

    @property
    def y(self) -> NDArray[np.uint8]:
        return self._arr["y"]


class BitPackedPayload(PayloadBase):
    _dtype: ClassVar = np.dtype([("packed", "u1")])

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "flag_a": (self._arr["packed"] & 0x01).astype(bool),
                "flag_b": ((self._arr["packed"] >> 1) & 0x01).astype(bool),
            }
        )


def _make_simple_bytes(n: int) -> bytes:
    arr = np.zeros(n, dtype=SimplePayload._dtype)
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
    arr = np.array([(0b00000011,), (0b00000001,), (0b00000010,)], dtype=BitPackedPayload._dtype)
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
        p._arr["x"][0] = 999


def test_payload_property():
    p = SimplePayload.from_buffer(_make_simple_bytes(2))
    assert p.payload.dtype == SimplePayload._dtype
