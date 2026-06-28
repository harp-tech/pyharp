"""Tests for the device layer: descriptors, to_dataframe, and read_frames."""

import enum
from typing import ClassVar

import numpy as np

from harp.data import to_dataframe
from harp.protocol._builder import build_message_frame
from harp.protocol._message_type import MessageType
from harp.protocol._payload import PayloadBase, BitMask, GroupMask
from harp.protocol._payload_type import PayloadType

from harp.device._registers import (
    EnableFlag,
    OperationControl,
    OperationControlPayload,
    OperationMode,
)


class Pins(enum.IntFlag):
    PIN0 = 0x01
    PIN1 = 0x02
    PIN2 = 0x04
    PIN3 = 0x08
    PIN4 = 0x10
    PIN5 = 0x20
    PIN6 = 0x40
    PIN7 = 0x80


class PinsPayload(PayloadBase[np.uint8]):
    pins = BitMask(enum=Pins, mask=0xFF)


# --- Minimal fixture payload class ------------------------------------------


class _FlagPayload(PayloadBase[np.uint8]):
    _dtype: ClassVar = np.dtype("u1")
    _repr_fields: ClassVar = ("flag", "group")

    flag = BitMask(enum=Pins, mask=0x01)
    group = GroupMask(mask=0x06, enum=OperationMode)


# --- BitMask behaviour ------------------------------------------------------


def test_bitmask_single_returns_flag_set():
    p = _FlagPayload.from_buffer(bytes([0x01]))
    assert p.flag == Pins.PIN0
    assert isinstance(p.flag, Pins)


def test_bitmask_single_returns_empty_flag():
    p = _FlagPayload.from_buffer(bytes([0x00]))
    assert p.flag == Pins(0)
    assert isinstance(p.flag, Pins)


def test_bitmask_batch_returns_raw_int_ndarray():
    p = _FlagPayload.from_buffer(bytes([0x01, 0x00, 0x01]))
    result = p.flag
    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, [1, 0, 1])


# --- GroupMask behaviour -----------------------------------------------------


def test_groupmask_single_returns_enum():
    p = _FlagPayload.from_buffer(bytes([0x02]))  # bits 1-2 = 01 -> Active
    result = p.group
    assert result == OperationMode.ACTIVE
    assert isinstance(result, OperationMode)


def test_groupmask_batch_returns_ndarray():
    p = _FlagPayload.from_buffer(bytes([0x00, 0x02, 0x06]))  # groups: 0, 1, 3
    result = p.group
    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, [0, 1, 3])


# --- OperationControlPayload -------------------------------------------------


def _make_op_ctrl_byte(
    mode: OperationMode = OperationMode.STANDBY,
    heartbeat: EnableFlag = EnableFlag.DISABLED,
) -> int:
    val = int(mode) & 0x03
    val |= (int(heartbeat) & 0x01) << 7
    return val


def test_op_ctrl_scalar_from_buffer():
    val = _make_op_ctrl_byte(OperationMode.ACTIVE, EnableFlag.ENABLED)
    p = OperationControlPayload.from_buffer(bytes([val]))
    assert p.operation_mode == OperationMode.ACTIVE
    assert p.heartbeat == EnableFlag.ENABLED
    assert p.dump_registers is False


def test_op_ctrl_init_matches_from_buffer():
    p_init = OperationControlPayload(
        operation_mode=OperationMode.ACTIVE, heartbeat=EnableFlag.ENABLED
    )
    val = _make_op_ctrl_byte(OperationMode.ACTIVE, EnableFlag.ENABLED)
    p_buf = OperationControlPayload.from_buffer(bytes([val]))
    assert p_init.operation_mode == p_buf.operation_mode
    assert p_init.heartbeat == p_buf.heartbeat


def test_op_ctrl_batch_descriptor_returns_ndarray():
    vals = [
        _make_op_ctrl_byte(OperationMode.ACTIVE, EnableFlag.ENABLED),
        _make_op_ctrl_byte(OperationMode.STANDBY, EnableFlag.DISABLED),
    ]
    p = OperationControlPayload.from_buffer(bytes(vals))
    assert isinstance(p.heartbeat, np.ndarray)
    np.testing.assert_array_equal(p.heartbeat, [True, False])


def test_op_ctrl_to_dataframe():
    vals = [
        _make_op_ctrl_byte(OperationMode.ACTIVE, EnableFlag.ENABLED),
        _make_op_ctrl_byte(OperationMode.STANDBY, EnableFlag.DISABLED),
    ]
    p = OperationControlPayload.from_buffer(bytes(vals))
    df = to_dataframe(p, decode_enums=False)
    assert list(df.columns) == list(OperationControlPayload._repr_fields)
    assert len(df) == 2
    np.testing.assert_array_equal(df["heartbeat"], [True, False])
    np.testing.assert_array_equal(
        df["operation_mode"],
        [int(OperationMode.ACTIVE), int(OperationMode.STANDBY)],
    )


# --- PinsPayload (cuttlefish) ------------------------------------------------


def test_pins_single_scalar():
    p = PinsPayload.from_buffer(bytes([0b00000101]))
    assert Pins.PIN0 in p.pins
    assert Pins.PIN1 not in p.pins
    assert Pins.PIN2 in p.pins
    assert Pins.PIN7 not in p.pins


def test_pins_batch_raw_int():
    p = PinsPayload.from_buffer(bytes([0b00000001, 0b00000010]))
    np.testing.assert_array_equal(p.pins, [0b01, 0b10])


def test_pins_to_dataframe_single_column():
    p = PinsPayload.from_buffer(bytes([0b00000101, 0b00000010]))
    df = to_dataframe(p)
    assert list(df.columns) == ["pins"]
    np.testing.assert_array_equal(df["pins"], [0b101, 0b10])
    assert len(df) == 2


def test_pins_to_dataframe_demuxed():
    p = PinsPayload.from_buffer(bytes([0b00000101, 0b00000010]))
    df = to_dataframe(p, demux_bit_masks=True)
    assert list(df.columns) == [m.name for m in Pins]
    np.testing.assert_array_equal(df["PIN0"], [True, False])
    np.testing.assert_array_equal(df["PIN1"], [False, True])
    np.testing.assert_array_equal(df["PIN2"], [True, False])


# --- read_frames round-trip --------------------------------------------------


def _make_frames(values: list, base_time: float = 1.0) -> bytes:
    """Build a raw binary buffer of N timestamped OperationControl frames."""
    frames = b""
    for i, v in enumerate(values):
        frames += build_message_frame(
            MessageType.Read,
            address=OperationControl.address,
            payload_type=PayloadType.U8,
            payload=bytes([v]),
            timestamp=base_time + i,
        )
    return frames


def _read_frames(raw: bytes):
    """Adapter over the current bulk API: returns (timestamps, payload)."""
    _data, timestamps, _msgtype, payload = OperationControl.parse_bulk(raw)
    if timestamps is None:
        timestamps = np.empty(0, dtype=np.float64)
    return timestamps, payload


def test_read_frames_count():
    raw = _make_frames([0x01, 0x00, 0x81])
    timestamps, payload = _read_frames(raw)
    assert len(timestamps) == 3
    assert len(payload) == 3


def test_read_frames_timestamps():
    raw = _make_frames([0x01, 0x00, 0x81], base_time=10.0)
    timestamps, _ = _read_frames(raw)
    np.testing.assert_allclose(timestamps, [10.0, 11.0, 12.0], atol=1e-4)


def test_read_frames_payload_type():
    raw = _make_frames([0x01])
    _, payload = _read_frames(raw)
    assert isinstance(payload, OperationControlPayload)


def test_read_frames_bitfield_batch():
    vals = [
        _make_op_ctrl_byte(OperationMode.ACTIVE, EnableFlag.ENABLED),
        _make_op_ctrl_byte(OperationMode.STANDBY, EnableFlag.DISABLED),
    ]
    raw = _make_frames(vals)
    _, payload = _read_frames(raw)
    np.testing.assert_array_equal(payload.heartbeat, [True, False])
    np.testing.assert_array_equal(
        payload.operation_mode,
        [int(OperationMode.ACTIVE), int(OperationMode.STANDBY)],
    )


def test_read_frames_to_dataframe():
    vals = [_make_op_ctrl_byte(OperationMode.ACTIVE), _make_op_ctrl_byte(), _make_op_ctrl_byte()]
    raw = _make_frames(vals)
    _, payload = _read_frames(raw)
    df = to_dataframe(payload)
    assert len(df) == 3
    assert "heartbeat" in df.columns
    assert "operation_mode" in df.columns


def test_read_frames_empty():
    timestamps, payload = _read_frames(b"")
    assert len(timestamps) == 0
    assert len(payload) == 0
