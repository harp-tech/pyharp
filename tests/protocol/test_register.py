"""Tests for _register.py and round-trips between register format/parse."""

from typing import ClassVar

import numpy as np
import pytest
from harp.protocol._message import HarpMessage
from harp.protocol._message_type import MessageType
from harp.protocol._payload import (
    PayloadBase,
    PayloadFloat,
    PayloadS8,
    PayloadS16,
    PayloadS32,
    PayloadS64,
    PayloadU8,
    PayloadU16,
    PayloadU32,
    PayloadU64,
)
from harp.protocol._payload_type import PayloadType
from harp.protocol._register import (
    RegisterBase,
    RegisterFloat,
    RegisterS8,
    RegisterS16,
    RegisterS16Array,
    RegisterS32,
    RegisterS64,
    RegisterU8,
    RegisterU16,
    RegisterU32,
    RegisterU32Array,
    RegisterU64,
)
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class TimestampSecond(RegisterU32):
    address: ClassVar[int] = 8


class DigitalOutputSet(RegisterU16):
    address: ClassVar[int] = 32


class AnalogDataPayload(PayloadBase):
    _dtype: ClassVar = np.dtype(
        [
            ("analog_input0", "<i2"),
            ("encoder", "<i2"),
            ("analog_input1", "<i2"),
        ]
    )

    @property
    def analog_input0(self) -> NDArray[np.int16]:
        return self._arr["analog_input0"]

    @property
    def encoder(self) -> NDArray[np.int16]:
        return self._arr["encoder"]

    @property
    def analog_input1(self) -> NDArray[np.int16]:
        return self._arr["analog_input1"]


class AnalogData(RegisterBase[AnalogDataPayload]):
    address: ClassVar[int] = 33
    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class: ClassVar = AnalogDataPayload


def _parse_frame(frame: bytes) -> HarpMessage:
    return HarpMessage.parse(frame)


@pytest.mark.parametrize(
    "reg_cls, address, payload_type, value, dtype",
    [
        (RegisterU8, 0x10, PayloadType.U8, 42, np.dtype("u1")),
        (RegisterU16, 0x11, PayloadType.U16, 1000, np.dtype("<u2")),
        (RegisterU32, 0x12, PayloadType.U32, 99999, np.dtype("<u4")),
        (RegisterU64, 0x13, PayloadType.U64, 2**32, np.dtype("<u8")),
        (RegisterS8, 0x14, PayloadType.S8, -5, np.dtype("i1")),
        (RegisterS16, 0x15, PayloadType.S16, -300, np.dtype("<i2")),
        (RegisterS32, 0x16, PayloadType.S32, -100000, np.dtype("<i4")),
        (RegisterS64, 0x17, PayloadType.S64, -(2**33), np.dtype("<i8")),
        (RegisterFloat, 0x18, PayloadType.Float, 3.14, np.dtype("<f4")),
    ],
)
def test_scalar_register_format_write(reg_cls, address, payload_type, value, dtype):
    """format(value) produces a parseable Write frame with the correct payload."""
    reg = reg_cls(address)
    frame = reg.format(value)
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Write
    assert msg.address == address
    assert msg.payload_type == payload_type
    expected = np.asarray(value, dtype=dtype).tobytes()
    assert msg.payload == expected


@pytest.mark.parametrize(
    "reg_cls, address, payload_type",
    [
        (RegisterU8, 0x10, PayloadType.U8),
        (RegisterU16, 0x11, PayloadType.U16),
        (RegisterU32, 0x12, PayloadType.U32),
        (RegisterU64, 0x13, PayloadType.U64),
        (RegisterS8, 0x14, PayloadType.S8),
        (RegisterS16, 0x15, PayloadType.S16),
        (RegisterS32, 0x16, PayloadType.S32),
        (RegisterS64, 0x17, PayloadType.S64),
        (RegisterFloat, 0x18, PayloadType.Float),
    ],
)
def test_scalar_register_format_read(reg_cls, address, payload_type):
    """format() (no value) produces a Read frame with empty payload."""
    reg = reg_cls(address)
    frame = reg.format()
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Read
    assert msg.address == address
    assert msg.payload == b""


@pytest.mark.parametrize("value", [0, 1, 2**32 - 1])
def test_named_register_roundtrip(value):
    """TimestampSecond write frame parses back to the same value."""
    frame = TimestampSecond.format(value)
    msg = _parse_frame(frame)
    parsed = TimestampSecond.parse(msg)
    assert isinstance(parsed, PayloadU32)
    assert parsed.value == np.array([value])


def test_named_register_format_read_frame():
    frame = TimestampSecond.format()
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Read
    assert msg.address == 8


def test_factory_creates_subclass():
    reg = RegisterU32(0x08)
    assert issubclass(reg, RegisterU32)
    assert reg.address == 0x08


def test_factory_format_and_parse():
    reg = RegisterU32(0x08)
    frame = reg.format(100)
    msg = _parse_frame(frame)
    parsed = reg.parse(msg)
    assert isinstance(parsed, PayloadU32)
    assert parsed.value == np.array([100])


def test_factory_different_addresses_are_independent():
    r1 = RegisterU32(0x08)
    r2 = RegisterU32(0x09)
    assert r1.address != r2.address
    assert r1 is not r2


@pytest.mark.parametrize(
    "reg_cls, payload_cls, value",
    [
        (RegisterU8, PayloadU8, 255),
        (RegisterU16, PayloadU16, 1000),
        (RegisterU32, PayloadU32, 123456),
        (RegisterS16, PayloadS16, -42),
        (RegisterFloat, PayloadFloat, 1.5),
    ],
)
def test_format_with_payload_instance(reg_cls, payload_cls, value):
    """Passing a PayloadXxx instance to format() uses the instance's bytes directly."""
    reg = reg_cls(0x08)
    payload = payload_cls(value)
    frame = reg.format(payload)
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Write
    assert msg.payload == payload.raw_payload.tobytes()


def test_format_with_payload_instance_via_register():
    """format() accepts a typed PayloadU32 and encodes it correctly."""
    payload = PayloadU32(42)
    frame = TimestampSecond.format(payload)
    msg = _parse_frame(frame)
    parsed = TimestampSecond.parse(msg)
    assert parsed.value == np.array([42])


def test_structured_register_parse_bulk():
    raw = np.array(
        [(100, 512, -200), (110, 513, -210), (120, 514, -220)],
        dtype=AnalogDataPayload._dtype,
    ).tobytes()

    bulk = AnalogData.parse_bulk(raw)
    assert isinstance(bulk, AnalogDataPayload)
    assert len(bulk) == 3
    np.testing.assert_array_equal(bulk.analog_input0, [100, 110, 120])
    np.testing.assert_array_equal(bulk.encoder, [512, 513, 514])
    np.testing.assert_array_equal(bulk.analog_input1, [-200, -210, -220])


def test_structured_register_parse_from_message_list():
    records = [(100, 512, -200), (110, 513, -210)]
    messages = []
    for rec in records:
        payload_bytes = np.array([rec], dtype=AnalogDataPayload._dtype).tobytes()
        msg = HarpMessage(
            MessageType.Event,
            AnalogData.address,
            AnalogData.payload_type,
            payload_bytes,
        )
        messages.append(msg)

    bulk = AnalogData.parse_bulk(messages)
    assert len(bulk) == 2
    np.testing.assert_array_equal(bulk.analog_input0, [100, 110])
    np.testing.assert_array_equal(bulk.encoder, [512, 513])
    np.testing.assert_array_equal(bulk.analog_input1, [-200, -210])


def test_structured_register_format_single_sample():
    sample = np.array([(100, 512, -200)], dtype=AnalogDataPayload._dtype)
    frame = AnalogData.format(sample)
    msg = _parse_frame(frame)
    parsed = AnalogData.parse(msg)
    assert isinstance(parsed, AnalogDataPayload)
    assert int(parsed.analog_input0[0]) == 100
    assert int(parsed.encoder[0]) == 512
    assert int(parsed.analog_input1[0]) == -200


def test_structured_register_to_dataframe():
    raw = np.array(
        [(1, 2, 3), (4, 5, 6)],
        dtype=AnalogDataPayload._dtype,
    ).tobytes()
    bulk = AnalogData.parse_bulk(raw)
    df = bulk.to_dataframe()
    assert list(df.columns) == ["analog_input0", "encoder", "analog_input1"]
    assert len(df) == 2
    assert df["analog_input0"].tolist() == [1, 4]


def test_array_register_factory_creates_subclass():
    reg = RegisterU32Array(0x08, length=3)
    assert issubclass(reg, RegisterU32Array)
    assert reg.address == 0x08
    assert reg.length == 3


def test_array_register_factory_different_lengths_independent():
    # Just to make sure there are no weird interactions when using the metaclass-base factory
    r1 = RegisterU32Array(0x08, length=2)
    r2 = RegisterU32Array(0x08, length=4)
    assert r1.length != r2.length
    assert r1.payload_class is not r2.payload_class


def test_array_register_format_write():
    reg = RegisterU32Array(0x08, length=3)
    values = np.array([10, 20, 30], dtype=np.dtype("<u4"))
    frame = reg.format(values)
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Write
    assert msg.payload == values.tobytes()


def test_array_register_parse_roundtrip():
    reg = RegisterU32Array(0x08, length=3)
    values = np.array([10, 20, 30], dtype=np.dtype("<u4"))
    frame = reg.format(values)
    msg = _parse_frame(frame)
    parsed = reg.parse(msg)
    # The payload array contains the packed sub-array as a single element
    flat = parsed.raw_payload.flatten().view(np.dtype("<u4"))
    np.testing.assert_array_equal(flat, values)


def test_s16_array_roundtrip():
    reg = RegisterS16Array(0x20, length=4)
    values = np.array([-1, 0, 1, 32767], dtype=np.dtype("<i2"))
    frame = reg.format(values)
    msg = _parse_frame(frame)
    parsed = reg.parse(msg)
    flat = parsed.raw_payload.flatten().view(np.dtype("<i2"))
    np.testing.assert_array_equal(flat, values)


def test_unnamed_register_auto_payload_class():
    """A bare RegisterU8 subclass with only address set gets an auto-generated payload class."""

    class MyReg(RegisterU8):
        address: ClassVar[int] = 0x50

    # payload_class should exist and parse correctly
    raw = np.array([7], dtype=np.dtype("u1")).tobytes()
    parsed = MyReg.parse(raw)
    assert parsed.value == np.array([7])


def test_explicit_payload_class_not_overwritten():
    """Explicit payload_class on AnalogData is not replaced by auto-generation."""
    assert AnalogData.payload_class is AnalogDataPayload


def test_format_read_override_message_type():
    frame = TimestampSecond.format(message_type=MessageType.Write)
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Write
    assert msg.payload == b""


def test_format_write_override_message_type():
    frame = TimestampSecond.format(42, message_type=MessageType.Event)
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Event


# ---------------------------------------------------------------------------
# 9. .value property
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload_cls, raw_value, np_dtype",
    [
        (PayloadU8, 255, np.dtype("u1")),
        (PayloadU16, 1000, np.dtype("<u2")),
        (PayloadU32, 99999, np.dtype("<u4")),
        (PayloadU64, 2**32, np.dtype("<u8")),
        (PayloadS8, -5, np.dtype("i1")),
        (PayloadS16, -300, np.dtype("<i2")),
        (PayloadS32, -100000, np.dtype("<i4")),
        (PayloadS64, -(2**33), np.dtype("<i8")),
        (PayloadFloat, 1.5, np.dtype("<f4")),
    ],
)
def test_scalar_payload_value_single(payload_cls, raw_value, np_dtype):
    buf = np.array([raw_value], dtype=np_dtype).tobytes()
    parsed = payload_cls.from_buffer(buf)
    assert len(parsed) == 1
    v = parsed.value
    assert np_dtype.type(raw_value) == v


@pytest.mark.parametrize(
    "payload_cls, np_dtype, values",
    [
        (PayloadU8, np.dtype("u1"), [1, 2, 3]),
        (PayloadS16, np.dtype("<i2"), [-1, 0, 1]),
        (PayloadU32, np.dtype("<u4"), [10, 20, 30]),
        (PayloadFloat, np.dtype("<f4"), [1.0, 2.0, 3.0]),
    ],
)
def test_scalar_payload_value_multi(payload_cls, np_dtype, values):
    """.value on a multi-element scalar payload returns the full backing array."""
    buf = np.array(values, dtype=np_dtype).tobytes()
    parsed = payload_cls.from_buffer(buf)
    assert len(parsed) == len(values)
    v = parsed.value
    assert isinstance(v, np.ndarray)
    np.testing.assert_array_equal(v, np.array(values, dtype=np_dtype))


def test_structured_payload_value_single():
    """.value on a single-record structured payload returns a numpy void (structured scalar)."""
    buf = np.array([(100, 512, -200)], dtype=AnalogDataPayload._dtype).tobytes()
    parsed = AnalogDataPayload.from_buffer(buf)
    assert len(parsed) == 1
    v = parsed.value
    assert v["analog_input0"] == np.array([100])
    assert v["encoder"] == np.array([512])
    assert v["analog_input1"] == np.array([-200])


def test_structured_payload_value_multi():
    """.value on a multi-record structured payload returns the full array."""
    records = [(100, 512, -200), (110, 513, -210), (120, 514, -220)]
    buf = np.array(records, dtype=AnalogDataPayload._dtype).tobytes()
    parsed = AnalogDataPayload.from_buffer(buf)
    assert len(parsed) == 3
    v = parsed.value
    assert isinstance(v, np.ndarray)
    assert v.dtype == AnalogDataPayload._dtype
    np.testing.assert_array_equal(v["analog_input0"], [100, 110, 120])
    np.testing.assert_array_equal(v["encoder"], [512, 513, 514])
    np.testing.assert_array_equal(v["analog_input1"], [-200, -210, -220])


def test_array_register_value_single():
    """.value on a single-record array-register payload returns a 1-D ndarray of the elements."""
    reg = RegisterU32Array(0x08, length=3)
    values = np.array([10, 20, 30], dtype=np.dtype("<u4"))
    frame = reg.format(values)
    msg = _parse_frame(frame)
    parsed = reg.parse(msg)
    # One sub-array record => len == 1 => .value returns arr[0], shape (3,)
    assert len(parsed) == 1
    v = parsed.value
    assert isinstance(v, np.ndarray)
    assert v.shape == (1, 3)
    np.testing.assert_array_equal(v, np.array([values]))


def test_array_register_value_multi():
    """.value on a multi-record array-register payload returns the full 2-D array."""
    reg = RegisterU32Array(0x08, length=3)
    # Two rows of 3 elements each; pass as flat bytes via parse_bulk
    rows = np.array([[10, 20, 30], [40, 50, 60]], dtype=np.dtype("<u4"))
    bulk = reg.parse_bulk(rows.tobytes())
    # Two sub-array records => len == 2 => .value returns the full array
    assert len(bulk) == 2
    v = bulk.value
    assert isinstance(v, np.ndarray)
    assert v.shape == (2, 3)
    np.testing.assert_array_equal(v[0], [10, 20, 30])
    np.testing.assert_array_equal(v[1], [40, 50, 60])
