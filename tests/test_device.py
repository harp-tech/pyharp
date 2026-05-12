"""Tests for the device layer: descriptors, to_dataframe, and read_frames."""

from typing import ClassVar

import numpy as np

from harp.protocol._builder import build_message_frame
from harp.protocol._message_type import MessageType
from harp.protocol._payload import PayloadBase, _BitFlag, _GroupMask
from harp.protocol._payload_type import PayloadType

from harp.device._registers import (
    EnableFlag,
    OperationControl,
    OperationControlPayload,
    OperationMode,
)


class PinsPayload(PayloadBase[np.uint8]):
    pin0 = _BitFlag(0x01)
    pin1 = _BitFlag(0x02)
    pin2 = _BitFlag(0x04)
    pin3 = _BitFlag(0x08)
    pin4 = _BitFlag(0x10)
    pin5 = _BitFlag(0x20)
    pin6 = _BitFlag(0x40)
    pin7 = _BitFlag(0x80)


# --- Minimal fixture payload class ------------------------------------------


class _FlagPayload(PayloadBase[np.uint8]):
    _dtype: ClassVar = np.dtype("u1")
    _repr_fields: ClassVar = ("flag", "group")

    flag = _BitFlag(0x01)
    group = _GroupMask(0x06, 1, OperationMode)


# --- _BitFlag behaviour ------------------------------------------------------


def test_bitflag_single_returns_bool_true():
    p = _FlagPayload.from_buffer(bytes([0x01]))
    assert p.flag is True
    assert type(p.flag) is bool


def test_bitflag_single_returns_bool_false():
    p = _FlagPayload.from_buffer(bytes([0x00]))
    assert p.flag is False
    assert type(p.flag) is bool


def test_bitflag_batch_returns_ndarray():
    p = _FlagPayload.from_buffer(bytes([0x01, 0x00, 0x01]))
    result = p.flag
    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, [True, False, True])


# --- _GroupMask behaviour ----------------------------------------------------


def test_groupmask_single_returns_enum():
    p = _FlagPayload.from_buffer(bytes([0x02]))  # bits 1-2 = 01 -> Active
    result = p.group
    assert result == OperationMode.Active
    assert isinstance(result, OperationMode)


def test_groupmask_batch_returns_ndarray():
    p = _FlagPayload.from_buffer(bytes([0x00, 0x02, 0x06]))  # groups: 0, 1, 3
    result = p.group
    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, [0, 1, 3])


# --- OperationControlPayload -------------------------------------------------


def _make_op_ctrl_byte(
    mode: OperationMode = OperationMode.Standby,
    heartbeat: EnableFlag = EnableFlag.Disabled,
) -> int:
    val = int(mode) & 0x03
    val |= (int(heartbeat) & 0x01) << 7
    return val


def test_op_ctrl_scalar_from_buffer():
    val = _make_op_ctrl_byte(OperationMode.Active, EnableFlag.Enabled)
    p = OperationControlPayload.from_buffer(bytes([val]))
    assert p.operation_mode == OperationMode.Active
    assert p.heartbeat == EnableFlag.Enabled
    assert p.dump_registers is False


def test_op_ctrl_init_matches_from_buffer():
    p_init = OperationControlPayload(
        operation_mode=OperationMode.Active, heartbeat=EnableFlag.Enabled
    )
    val = _make_op_ctrl_byte(OperationMode.Active, EnableFlag.Enabled)
    p_buf = OperationControlPayload.from_buffer(bytes([val]))
    assert p_init.operation_mode == p_buf.operation_mode
    assert p_init.heartbeat == p_buf.heartbeat


def test_op_ctrl_batch_descriptor_returns_ndarray():
    vals = [
        _make_op_ctrl_byte(OperationMode.Active, EnableFlag.Enabled),
        _make_op_ctrl_byte(OperationMode.Standby, EnableFlag.Disabled),
    ]
    p = OperationControlPayload.from_buffer(bytes(vals))
    assert isinstance(p.heartbeat, np.ndarray)
    np.testing.assert_array_equal(p.heartbeat, [True, False])


def test_op_ctrl_to_dataframe():
    vals = [
        _make_op_ctrl_byte(OperationMode.Active, EnableFlag.Enabled),
        _make_op_ctrl_byte(OperationMode.Standby, EnableFlag.Disabled),
    ]
    p = OperationControlPayload.from_buffer(bytes(vals))
    df = p.to_dataframe()
    assert list(df.columns) == list(OperationControlPayload._repr_fields)
    assert len(df) == 2
    np.testing.assert_array_equal(df["heartbeat"], [True, False])
    np.testing.assert_array_equal(
        df["operation_mode"],
        [int(OperationMode.Active), int(OperationMode.Standby)],
    )


# --- PinsPayload (cuttlefish) ------------------------------------------------


def test_pins_single_scalar():
    p = PinsPayload.from_buffer(bytes([0b00000101]))
    assert p.pin0 is True
    assert p.pin1 is False
    assert p.pin2 is True
    assert p.pin7 is False


def test_pins_batch_ndarray():
    p = PinsPayload.from_buffer(bytes([0b00000001, 0b00000010]))
    np.testing.assert_array_equal(p.pin0, [True, False])
    np.testing.assert_array_equal(p.pin1, [False, True])


def test_pins_to_dataframe():
    p = PinsPayload.from_buffer(bytes([0b00000101, 0b00000010]))
    df = p.to_dataframe()
    assert list(df.columns) == list(PinsPayload._repr_fields)
    assert len(df) == 2


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


def test_read_frames_count():
    raw = _make_frames([0x01, 0x00, 0x81])
    timestamps, payload = OperationControl.read_frames(raw)
    assert len(timestamps) == 3
    assert len(payload) == 3


def test_read_frames_timestamps():
    raw = _make_frames([0x01, 0x00, 0x81], base_time=10.0)
    timestamps, _ = OperationControl.read_frames(raw)
    np.testing.assert_allclose(timestamps, [10.0, 11.0, 12.0], atol=1e-4)


def test_read_frames_payload_type():
    raw = _make_frames([0x01])
    _, payload = OperationControl.read_frames(raw)
    assert isinstance(payload, OperationControlPayload)


def test_read_frames_bitfield_batch():
    vals = [
        _make_op_ctrl_byte(OperationMode.Active, EnableFlag.Enabled),
        _make_op_ctrl_byte(OperationMode.Standby, EnableFlag.Disabled),
    ]
    raw = _make_frames(vals)
    _, payload = OperationControl.read_frames(raw)
    np.testing.assert_array_equal(payload.heartbeat, [True, False])
    np.testing.assert_array_equal(
        payload.operation_mode,
        [int(OperationMode.Active), int(OperationMode.Standby)],
    )


def test_read_frames_to_dataframe():
    vals = [_make_op_ctrl_byte(OperationMode.Active), _make_op_ctrl_byte(), _make_op_ctrl_byte()]
    raw = _make_frames(vals)
    _, payload = OperationControl.read_frames(raw)
    df = payload.to_dataframe()
    assert len(df) == 3
    assert "heartbeat" in df.columns
    assert "operation_mode" in df.columns


def test_read_frames_empty():
    timestamps, payload = OperationControl.read_frames(b"")
    assert len(timestamps) == 0
    assert len(payload) == 0
