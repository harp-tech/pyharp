import enum
from typing import ClassVar

import numpy as np
from harp.protocol._payload import (
    PayloadBase,
    _BitFlag,
    _Field,
    _GroupMask,
    _StringConverter,
)
from harp.protocol._payload_type import PayloadType
from harp.protocol._register import RegisterBase, RegisterU8, RegisterU16, RegisterU32


class OperationMode(enum.IntEnum):
    """Specifies the operation mode of the device."""

    Standby = 0
    Active = 1
    Speed = 3


class EnableFlag(enum.IntEnum):
    """Specifies whether a specific register flag is enabled or disabled."""

    Disabled = 0
    Enabled = 1


# ---------------------------------------------------------------------------
# Complex payload classes
# ---------------------------------------------------------------------------


class OperationControlPayload(PayloadBase[np.uint8]):
    operation_mode = _GroupMask(0x03, 0, OperationMode, dtype=np.uint8)
    dump_registers = _BitFlag(0x08, dtype=np.uint8)
    mute_replies = _BitFlag(0x10, dtype=np.uint8)
    visual_indicators = _GroupMask(0x20, 5, EnableFlag, dtype=np.uint8)
    operation_led = _GroupMask(0x40, 6, EnableFlag, dtype=np.uint8)
    heartbeat = _GroupMask(0x80, 7, EnableFlag, dtype=np.uint8)


class ResetDevicePayload(PayloadBase[np.uint8]):
    """Payload for the ResetDevice register (address 11)."""

    restore_default = _BitFlag(0x01, dtype=np.uint8)
    restore_eeprom = _BitFlag(0x02, dtype=np.uint8)
    save = _BitFlag(0x04, dtype=np.uint8)
    restore_name = _BitFlag(0x08, dtype=np.uint8)
    update_firmware = _BitFlag(0x20, dtype=np.uint8)
    boot_from_default = _BitFlag(0x40, dtype=np.uint8)
    boot_from_eeprom = _BitFlag(0x80, dtype=np.uint8)


class DeviceNamePayload(PayloadBase[np.uint8]):
    """Payload for the DeviceName register (address 12).

    Stores a user-specified ASCII device name padded to 25 bytes. Encoding,
    decoding, and the dataframe column are all handled by ``_StringConverter``.
    """

    _MAX_LEN: ClassVar[int] = 25

    value = _Field(_StringConverter(_MAX_LEN))


class ClockConfigPayload(PayloadBase[np.uint8]):
    """Payload for the ClockConfiguration register (address 14)."""

    clock_repeater = _BitFlag(0x01, dtype=np.uint8)
    clock_generator = _BitFlag(0x02, dtype=np.uint8)
    repeater_capability = _BitFlag(0x08, dtype=np.uint8)
    generator_capability = _BitFlag(0x10, dtype=np.uint8)
    clock_unlock = _BitFlag(0x40, dtype=np.uint8)
    clock_lock = _BitFlag(0x80, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------


class WhoAmI(RegisterU16):
    address: ClassVar[int] = 0


class TimestampSecond(RegisterU32):
    address: ClassVar[int] = 8


class TimestampMicro(RegisterU16):
    address: ClassVar[int] = 9


class OperationControl(RegisterBase[OperationControlPayload]):
    address: ClassVar[int] = 10
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class: ClassVar[type[PayloadBase]] = OperationControlPayload


class ResetDevice(RegisterBase[ResetDevicePayload]):
    address: ClassVar[int] = 11
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class: ClassVar[type[PayloadBase]] = ResetDevicePayload


class DeviceName(RegisterBase[DeviceNamePayload]):
    address: ClassVar[int] = 12
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class: ClassVar[type[PayloadBase]] = DeviceNamePayload


class ClockConfig(RegisterBase[ClockConfigPayload]):
    address: ClassVar[int] = 14
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class: ClassVar[type[PayloadBase]] = ClockConfigPayload


class Heartbeat(RegisterU16):
    address: ClassVar[int] = 18


# ── Deprecated ───────────────────────


class HwVersionH(RegisterU8):
    address: ClassVar[int] = 1


class HwVersionL(RegisterU8):
    address: ClassVar[int] = 2


class AssemblyVersion(RegisterU8):
    address: ClassVar[int] = 3


class CoreVersionH(RegisterU8):
    address: ClassVar[int] = 4


class CoreVersionL(RegisterU8):
    address: ClassVar[int] = 5


class FirmwareVersionH(RegisterU8):
    address: ClassVar[int] = 6


class FirmwareVersionL(RegisterU8):
    address: ClassVar[int] = 7


class SerialNumber(RegisterU16):
    address: ClassVar[int] = 13


class TimestampOffset(RegisterU8):
    address: ClassVar[int] = 15
