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
    _Field,
    _IdentityConverter,
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
# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class TimestampSecond(RegisterU32):
    address: ClassVar[int] = 8


class DigitalOutputSet(RegisterU16):
    address: ClassVar[int] = 32


class AnalogDataPayload(PayloadBase):
    analog_input0 = _Field(_IdentityConverter("<i2"))
    encoder = _Field(_IdentityConverter("<i2"))
    analog_input1 = _Field(_IdentityConverter("<i2"))


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
    # parse() returns a 0-D scalar; compare to the Python value directly.
    assert parsed.value == value
    assert parsed.value.ndim == 0


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
    assert parsed.value == 100
    assert parsed.value.ndim == 0


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
    assert parsed.value == 42


def test_structured_register_format_single_sample():
    sample = np.array([(100, 512, -200)], dtype=AnalogDataPayload._dtype)
    frame = AnalogData.format(sample)
    msg = _parse_frame(frame)
    parsed = AnalogData.parse(msg)
    assert isinstance(parsed, AnalogDataPayload)
    # parse() yields a 0-D record; @property accessors return numpy scalars.
    assert int(parsed.analog_input0) == 100
    assert int(parsed.encoder) == 512
    assert int(parsed.analog_input1) == -200


def test_structured_register_to_dataframe():
    raw = np.array(
        [(1, 2, 3), (4, 5, 6)],
        dtype=AnalogDataPayload._dtype,
    ).tobytes()
    # Bulk decode goes through .Batch; from_buffer handles the redirect.
    bulk = AnalogDataPayload.from_buffer(raw)
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
    # parse() yields a 0-D record holding one length-3 sub-array.
    np.testing.assert_array_equal(parsed.value, values)
    assert parsed.value.shape == (3,)


def test_s16_array_roundtrip():
    reg = RegisterS16Array(0x20, length=4)
    values = np.array([-1, 0, 1, 32767], dtype=np.dtype("<i2"))
    frame = reg.format(values)
    msg = _parse_frame(frame)
    parsed = reg.parse(msg)
    np.testing.assert_array_equal(parsed.value, values)
    assert parsed.value.shape == (4,)


def test_unnamed_register_auto_payload_class():
    """A bare RegisterU8 subclass with only address set gets an auto-generated payload class."""

    class MyReg(RegisterU8):
        address: ClassVar[int] = 0x50

    # payload_class should exist and parse correctly
    raw = np.array([7], dtype=np.dtype("u1")).tobytes()
    parsed = MyReg.parse(raw)
    assert parsed.value == 7


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


def test_format_read_with_timestamp():
    ts = 12.5
    frame = TimestampSecond.format(timestamp=ts)
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Read
    assert msg.has_timestamp
    assert msg.timestamp == pytest.approx(ts, abs=1e-4)


def test_format_write_with_timestamp():
    ts = 100.0
    frame = TimestampSecond.format(42, timestamp=ts)
    msg = _parse_frame(frame)
    assert msg.message_type == MessageType.Write
    assert msg.has_timestamp
    assert msg.timestamp == pytest.approx(ts, abs=1e-4)
    parsed = TimestampSecond.parse(msg)
    assert parsed.value == 42


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
    """.value on a parse() result for an array register: 1-D length-N sub-array."""
    reg = RegisterU32Array(0x08, length=3)
    values = np.array([10, 20, 30], dtype=np.dtype("<u4"))
    frame = reg.format(values)
    msg = _parse_frame(frame)
    parsed = reg.parse(msg)
    assert len(parsed) == 1
    v = parsed.value
    assert isinstance(v, np.ndarray)
    assert v.shape == (3,)
    np.testing.assert_array_equal(v, values)


def test_array_register_value_multi():
    """.value on a Batch payload for an array register: 2-D (N, length) ndarray."""
    reg = RegisterU32Array(0x08, length=3)
    rows = np.array([[10, 20, 30], [40, 50, 60]], dtype=np.dtype("<u4"))
    # Bulk decode → goes through .Batch (1-D _arr of length 2).
    bulk = reg.payload_class.from_buffer(rows.tobytes())
    assert len(bulk) == 2
    v = bulk.value
    assert isinstance(v, np.ndarray)
    assert v.shape == (2, 3)
    np.testing.assert_array_equal(v[0], [10, 20, 30])
    np.testing.assert_array_equal(v[1], [40, 50, 60])


# ---------------------------------------------------------------------------
# 10. parse vs read_frames / .Batch contract
# ---------------------------------------------------------------------------


def test_parse_returns_zero_dim_arr():
    """parse() always wraps a single record in a 0-D _arr on the scalar class."""
    frame = TimestampSecond.format(42)
    msg = _parse_frame(frame)
    parsed = TimestampSecond.parse(msg)
    assert parsed._arr.ndim == 0
    assert isinstance(parsed, PayloadU32)
    # parse() routes 0-D records to the scalar twin (PayloadU32); the auto-
    # derived PayloadU32.Batch only handles 1-D buffers.
    assert type(parsed) is PayloadU32


def test_parse_does_not_overrun_buffer():
    """parse() reads exactly one record even if the buffer is larger."""
    # Two-record buffer in raw form (no Harp header — exercise PayloadBase path).
    raw = np.array([42, 99], dtype=np.dtype("<u4")).tobytes()
    parsed = TimestampSecond.parse(raw)
    assert parsed.value == 42
    assert parsed._arr.ndim == 0
    assert len(parsed) == 1


def test_batch_payload_routes_to_batch_twin():
    """from_buffer wraps a 1-D _arr in the auto-derived ``Batch`` twin.

    The Batch class is a subclass of the scalar class with each descriptor
    swapped to its ``*Batch`` counterpart, so ``isinstance(batch, scalar_cls)``
    still holds while ``type(batch)`` is the Batch sibling.
    """
    reg = RegisterU32Array(0x08, length=3)
    rows = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.dtype("<u4"))
    batch = reg.payload_class.from_buffer(rows.tobytes())
    assert type(batch) is reg.payload_class.Batch
    assert isinstance(batch, reg.payload_class)
    assert batch._arr.ndim == 1


def test_struct_payload_field_descriptors_codegen_style():
    """A struct payload declared via _Field descriptors decodes both ndim modes."""

    class GeneratedAnalogPayload(PayloadBase):
        a = _Field(_IdentityConverter("<i2"))
        b = _Field(_IdentityConverter("<i2"))
        c = _Field(_IdentityConverter("<i2"))

    p = GeneratedAnalogPayload.from_array(np.array((1, 2, 3), dtype=GeneratedAnalogPayload._dtype))
    # 0-D _arr → numpy scalar per field.
    assert int(p.a) == 1
    assert int(p.b) == 2
    assert int(p.c) == 3

    # 1-D _arr → ndarray columns. Same descriptor handles both.
    batch_arr = np.array([(1, 2, 3), (4, 5, 6)], dtype=GeneratedAnalogPayload._dtype)
    batch = GeneratedAnalogPayload.from_buffer(batch_arr.tobytes())
    np.testing.assert_array_equal(batch.a, [1, 4])
    np.testing.assert_array_equal(batch.b, [2, 5])
    assert batch._arr.ndim == 1


def test_repr_fields_auto_derived_from_dtype():
    """A struct payload that doesn't set _repr_fields gets them from _dtype.names."""

    class P(PayloadBase):
        alpha = _Field(_IdentityConverter("<i2"))
        beta = _Field(_IdentityConverter("<u1"))

    assert P._repr_fields == ("alpha", "beta")
