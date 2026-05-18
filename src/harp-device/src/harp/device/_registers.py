import enum
from typing import ClassVar

import numpy as np
from harp.protocol._payload import StructPayload, _BitFlag, _Field, _GroupMask
from harp.protocol._payload_converters import StringConverter as _StringConverter
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


class OperationControlPayload(StructPayload[np.uint8]):
    operation_mode: OperationMode = _GroupMask(
        mask=0x03, shift=0, enum=OperationMode, dtype=np.uint8, default=OperationMode.Standby
    )
    dump_registers: bool = _BitFlag(mask=0x08, dtype=np.uint8, default=False)
    mute_replies: bool = _BitFlag(mask=0x10, dtype=np.uint8, default=False)
    visual_indicators: EnableFlag = _GroupMask(
        mask=0x20, shift=5, enum=EnableFlag, dtype=np.uint8, default=EnableFlag.Disabled
    )
    operation_led: EnableFlag = _GroupMask(
        mask=0x40, shift=6, enum=EnableFlag, dtype=np.uint8, default=EnableFlag.Disabled
    )
    heartbeat: EnableFlag = _GroupMask(
        mask=0x80, shift=7, enum=EnableFlag, dtype=np.uint8, default=EnableFlag.Disabled
    )


class ResetDevicePayload(StructPayload[np.uint8]):
    """Payload for the ResetDevice register (address 11)."""

    restore_default: bool = _BitFlag(mask=0x01, dtype=np.uint8, default=False)
    restore_eeprom: bool = _BitFlag(mask=0x02, dtype=np.uint8, default=False)
    save: bool = _BitFlag(mask=0x04, dtype=np.uint8, default=False)
    restore_name: bool = _BitFlag(mask=0x08, dtype=np.uint8, default=False)
    update_firmware: bool = _BitFlag(mask=0x20, dtype=np.uint8, default=False)
    boot_from_default: bool = _BitFlag(mask=0x40, dtype=np.uint8, default=False)
    boot_from_eeprom: bool = _BitFlag(mask=0x80, dtype=np.uint8, default=False)


class DeviceNamePayload(StructPayload[np.uint8]):
    """Payload for the DeviceName register (address 12).

    Stores a user-specified ASCII device name padded to 25 bytes.
    """

    _MAX_LEN: ClassVar[int] = 25

    value: str = _Field(converter=_StringConverter(_MAX_LEN))


class ClockConfigPayload(StructPayload[np.uint8]):
    """Payload for the ClockConfiguration register (address 14)."""

    clock_repeater: bool = _BitFlag(mask=0x01, dtype=np.uint8, default=False)
    clock_generator: bool = _BitFlag(mask=0x02, dtype=np.uint8, default=False)
    repeater_capability: bool = _BitFlag(mask=0x08, dtype=np.uint8, default=False)
    generator_capability: bool = _BitFlag(mask=0x10, dtype=np.uint8, default=False)
    clock_unlock: bool = _BitFlag(mask=0x40, dtype=np.uint8, default=False)
    clock_lock: bool = _BitFlag(mask=0x80, dtype=np.uint8, default=False)


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
    payload_class = OperationControlPayload


class ResetDevice(RegisterBase[ResetDevicePayload]):
    address: ClassVar[int] = 11
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ResetDevicePayload


class DeviceName(RegisterBase[DeviceNamePayload]):
    address: ClassVar[int] = 12
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = DeviceNamePayload


class ClockConfig(RegisterBase[ClockConfigPayload]):
    address: ClassVar[int] = 14
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ClockConfigPayload


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
