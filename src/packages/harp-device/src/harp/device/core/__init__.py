# This file was automatically generated and should not be edited directly.
# To make changes, edit the device metadata and regenerate the interface.

"""The core register set every Harp device carries, and its address space."""

import enum
from typing import Any, ClassVar

import numpy as np
from harp.protocol import (
    AnonymousPayload,
    BitMask,
    BoolConverter,
    Field,
    GroupMask,
    PayloadType,
    RegisterBase,
    RegisterU16,
    RegisterU32,
    RegisterU8,
    StringConverter,
    StructPayload,
)


__all__ = [
    "ResetFlags",
    "ClockConfigurationFlags",
    "OperationMode",
    "EnableFlag",
    "OperationControlPayload",
    "ResetDevicePayload",
    "DeviceNamePayload",
    "ClockConfigurationPayload",
    "WhoAmI",
    "HardwareVersionHigh",
    "HardwareVersionLow",
    "AssemblyVersion",
    "CoreVersionHigh",
    "CoreVersionLow",
    "FirmwareVersionHigh",
    "FirmwareVersionLow",
    "TimestampSeconds",
    "TimestampMicroseconds",
    "OperationControl",
    "ResetDevice",
    "DeviceName",
    "SerialNumber",
    "ClockConfiguration",
    "REGISTER_MAP",
]


class ResetFlags(enum.IntFlag):
    """Specifies the behavior of the non-volatile registers when resetting the device."""

    RESTORE_DEFAULT = 0x1
    """The device will boot with all the registers reset to their default factory values."""

    RESTORE_EEPROM = 0x2
    """The device will boot and restore all the registers to the values stored in non-volatile memory."""

    SAVE = 0x4
    """The device will boot and save all the current register values to non-volatile memory."""

    RESTORE_NAME = 0x8
    """The device will boot with the default device name."""

    UPDATE_FIRMWARE = 0x20
    """The device will enter firmware update mode."""

    BOOT_FROM_DEFAULT = 0x40
    """Specifies that the device has booted from default factory values."""

    BOOT_FROM_EEPROM = 0x80
    """Specifies that the device has booted from non-volatile values stored in EEPROM."""


class ClockConfigurationFlags(enum.IntFlag):
    """Specifies configuration flags for the device synchronization clock."""

    CLOCK_REPEATER = 0x1
    """The device will repeat the clock synchronization signal to the clock output connector, if available."""

    CLOCK_GENERATOR = 0x2
    """The device resets and generates the clock synchronization signal on the clock output connector, if available."""

    REPEATER_CAPABILITY = 0x8
    """Specifies the device has the capability to repeat the clock synchronization signal to the clock output connector."""

    GENERATOR_CAPABILITY = 0x10
    """Specifies the device has the capability to generate the clock synchronization signal to the clock output connector."""

    CLOCK_UNLOCK = 0x40
    """The device will unlock the timestamp register counter and will accept commands to set new timestamp values."""

    CLOCK_LOCK = 0x80
    """The device will lock the timestamp register counter and will not accept commands to set new timestamp values."""


class OperationMode(enum.IntEnum):
    """Specifies the operation mode of the device."""

    STANDBY = 0
    """Disable all event reporting on the device."""

    ACTIVE = 1
    """Event detection is enabled. Only enabled events are reported by the device."""

    SPEED = 3
    """The device enters speed mode."""


class EnableFlag(enum.IntEnum):
    """Specifies whether a specific register flag is enabled or disabled."""

    DISABLED = 0
    """Specifies that the flag is disabled."""

    ENABLED = 1
    """Specifies that the flag is enabled."""


class OperationControlPayload(StructPayload[np.uint8]):
    """Represents the payload of the OperationControl register."""

    operation_mode: OperationMode = GroupMask(enum=OperationMode, mask=0x3)
    """Specifies the operation mode of the device."""

    dump_registers: bool = Field(BoolConverter(), mask=0x8)
    """Specifies whether the device should report the content of all registers on initialization."""

    mute_replies: bool = Field(BoolConverter(), mask=0x10)
    """Specifies whether the replies to all commands will be muted, i.e. not sent by the device."""

    visual_indicators: EnableFlag = GroupMask(enum=EnableFlag, mask=0x20)
    """Specifies the state of all visual indicators on the device."""

    operation_led: EnableFlag = GroupMask(enum=EnableFlag, mask=0x40)
    """Specifies whether the device state LED should report the operation mode of the device."""

    heartbeat: EnableFlag = GroupMask(enum=EnableFlag, mask=0x80)
    """Specifies whether the device should report the content of the seconds register each second."""


class ResetDevicePayload(AnonymousPayload[np.uint8]):
    """Represents the payload of the ResetDevice register."""

    __value__: ResetFlags = BitMask(enum=ResetFlags)


class DeviceNamePayload(AnonymousPayload[np.uint8]):
    """Represents the payload of the DeviceName register."""

    __value__: str = Field(StringConverter(25))


class ClockConfigurationPayload(AnonymousPayload[np.uint8]):
    """Represents the payload of the ClockConfiguration register."""

    __value__: ClockConfigurationFlags = BitMask(enum=ClockConfigurationFlags)


class WhoAmI(RegisterU16):
    """Specifies the identity class of the device."""

    address: ClassVar[int] = 0


class HardwareVersionHigh(RegisterU8):
    """Specifies the major hardware version of the device."""

    address: ClassVar[int] = 1


class HardwareVersionLow(RegisterU8):
    """Specifies the minor hardware version of the device."""

    address: ClassVar[int] = 2


class AssemblyVersion(RegisterU8):
    """Specifies the version of the assembled components in the device."""

    address: ClassVar[int] = 3


class CoreVersionHigh(RegisterU8):
    """Specifies the major version of the Harp core implemented by the device."""

    address: ClassVar[int] = 4


class CoreVersionLow(RegisterU8):
    """Specifies the minor version of the Harp core implemented by the device."""

    address: ClassVar[int] = 5


class FirmwareVersionHigh(RegisterU8):
    """Specifies the major version of the Harp core implemented by the device."""

    address: ClassVar[int] = 6


class FirmwareVersionLow(RegisterU8):
    """Specifies the minor version of the Harp core implemented by the device."""

    address: ClassVar[int] = 7


class TimestampSeconds(RegisterU32):
    """Stores the integral part of the system timestamp, in seconds."""

    address: ClassVar[int] = 8


class TimestampMicroseconds(RegisterU16):
    """Stores the fractional part of the system timestamp, in microseconds."""

    address: ClassVar[int] = 9


class OperationControl(RegisterBase[OperationControlPayload]):
    """Stores the configuration mode of the device."""

    address: ClassVar[int] = 10
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = OperationControlPayload


class ResetDevice(RegisterBase[ResetFlags]):
    """Resets the device and saves non-volatile registers."""

    address: ClassVar[int] = 11
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ResetDevicePayload


class DeviceName(RegisterBase[str]):
    """Stores the user-specified device name."""

    address: ClassVar[int] = 12
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = DeviceNamePayload


class SerialNumber(RegisterU16):
    """Specifies the unique serial number of the device."""

    address: ClassVar[int] = 13


class ClockConfiguration(RegisterBase[ClockConfigurationFlags]):
    """Specifies the configuration for the device synchronization clock."""

    address: ClassVar[int] = 14
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ClockConfigurationPayload


REGISTER_MAP: dict[int, type[RegisterBase[Any]]] = {
    0: WhoAmI,
    1: HardwareVersionHigh,
    2: HardwareVersionLow,
    3: AssemblyVersion,
    4: CoreVersionHigh,
    5: CoreVersionLow,
    6: FirmwareVersionHigh,
    7: FirmwareVersionLow,
    8: TimestampSeconds,
    9: TimestampMicroseconds,
    10: OperationControl,
    11: ResetDevice,
    12: DeviceName,
    13: SerialNumber,
    14: ClockConfiguration,
}
