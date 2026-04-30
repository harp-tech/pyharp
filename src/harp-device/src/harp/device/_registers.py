import enum
from typing import ClassVar

import numpy as np
import pandas as pd
from harp.protocol._payload import PayloadBase
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
    _dtype: ClassVar = np.dtype("u1")
    _repr_fields: ClassVar = (
        "operation_mode",
        "dump_registers",
        "mute_replies",
        "visual_indicators",
        "operation_led",
        "heartbeat",
    )

    def __init__(
        self,
        *,
        operation_mode: OperationMode | int = OperationMode.Standby,
        dump_registers: bool = False,
        mute_replies: bool = False,
        visual_indicators: EnableFlag | int = EnableFlag.Disabled,
        operation_led: EnableFlag | int = EnableFlag.Disabled,
        heartbeat: EnableFlag | int = EnableFlag.Disabled,
    ) -> None:
        val = np.uint8(0)
        val |= np.uint8(operation_mode) & np.uint8(0x03)
        val |= np.uint8(dump_registers) << np.uint8(3)
        val |= np.uint8(mute_replies) << np.uint8(4)
        val |= (np.uint8(visual_indicators) & np.uint8(0x01)) << np.uint8(5)
        val |= (np.uint8(operation_led) & np.uint8(0x01)) << np.uint8(6)
        val |= (np.uint8(heartbeat) & np.uint8(0x01)) << np.uint8(7)
        self._arr = np.array([val], dtype=self._dtype)

    @property
    def operation_mode(self) -> np.ndarray:
        return self._arr & np.uint8(0x03)

    @property
    def dump_registers(self) -> np.ndarray:
        return (self._arr >> 3) & np.uint8(0x01)

    @property
    def mute_replies(self) -> np.ndarray:
        return (self._arr >> 4) & np.uint8(0x01)

    @property
    def visual_indicators(self) -> np.ndarray:
        return (self._arr >> 5) & np.uint8(0x01)

    @property
    def operation_led(self) -> np.ndarray:
        return (self._arr >> 6) & np.uint8(0x01)

    @property
    def heartbeat(self) -> np.ndarray:
        return (self._arr >> 7) & np.uint8(0x01)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "operation_mode": [self.operation_mode],
                "dump_registers": [self.dump_registers],
                "mute_replies": [self.mute_replies],
                "visual_indicators": [self.visual_indicators],
                "operation_led": [self.operation_led],
                "heartbeat": [self.heartbeat],
            }
        )


class ResetDevicePayload(PayloadBase[np.uint8]):
    """Payload for the ResetDevice register (address 11)."""

    _dtype: ClassVar = np.dtype("u1")
    _repr_fields: ClassVar = (
        "restore_default",
        "restore_eeprom",
        "save",
        "restore_name",
        "update_firmware",
        "boot_from_default",
        "boot_from_eeprom",
    )

    def __init__(
        self,
        *,
        restore_default: bool = False,
        restore_eeprom: bool = False,
        save: bool = False,
        restore_name: bool = False,
        update_firmware: bool = False,
        boot_from_default: bool = False,
        boot_from_eeprom: bool = False,
    ) -> None:
        val = np.uint8(0)
        val |= np.uint8(restore_default) << np.uint8(0)
        val |= np.uint8(restore_eeprom) << np.uint8(1)
        val |= np.uint8(save) << np.uint8(2)
        val |= np.uint8(restore_name) << np.uint8(3)
        val |= np.uint8(update_firmware) << np.uint8(5)
        val |= np.uint8(boot_from_default) << np.uint8(6)
        val |= np.uint8(boot_from_eeprom) << np.uint8(7)
        self._arr = np.array([val], dtype=self._dtype)

    @property
    def restore_default(self) -> bool:
        return bool(self._arr & np.uint8(0x01))

    @property
    def restore_eeprom(self) -> bool:
        return bool(self._arr & np.uint8(0x02))

    @property
    def save(self) -> bool:
        return bool(self._arr & np.uint8(0x04))

    @property
    def restore_name(self) -> bool:
        return bool(self._arr & np.uint8(0x08))

    @property
    def update_firmware(self) -> bool:
        return bool(self._arr & np.uint8(0x20))

    @property
    def boot_from_default(self) -> bool:
        return bool(self._arr & np.uint8(0x40))

    @property
    def boot_from_eeprom(self) -> bool:
        return bool(self._arr & np.uint8(0x80))

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "restore_default": self.restore_default,
                "restore_eeprom": self.restore_eeprom,
                "save": self.save,
                "restore_name": self.restore_name,
                "update_firmware": self.update_firmware,
                "boot_from_default": self.boot_from_default,
                "boot_from_eeprom": self.boot_from_eeprom,
            }
        )


class DeviceNamePayload(PayloadBase[np.uint8]):
    """Payload for the DeviceName register (address 12).

    Stores a user-specified ASCII device name padded to 25 bytes.
    Access the decoded string via ``.name``; ``.value`` returns the raw byte array.
    """

    _dtype: ClassVar = np.dtype("u1")
    _repr_fields: ClassVar = ("name",)
    _MAX_LEN: ClassVar[int] = 25

    def __init__(self, name: str) -> None:
        encoded = name.encode("ascii")[: self._MAX_LEN]
        padded = encoded.ljust(self._MAX_LEN, b"\x00")
        self._arr = np.frombuffer(padded, dtype=self._dtype).copy()

    @property
    def name(self) -> str:
        return self._arr.tobytes().rstrip(b"\x00").decode("ascii")

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({"name": [self.name]})


class ClockConfigPayload(PayloadBase[np.uint8]):
    """Payload for the ClockConfiguration register (address 14)."""

    _dtype: ClassVar = np.dtype("u1")
    _repr_fields: ClassVar = (
        "clock_repeater",
        "clock_generator",
        "repeater_capability",
        "generator_capability",
        "clock_unlock",
        "clock_lock",
    )

    def __init__(
        self,
        *,
        clock_repeater: bool = False,
        clock_generator: bool = False,
        repeater_capability: bool = False,
        generator_capability: bool = False,
        clock_unlock: bool = False,
        clock_lock: bool = False,
    ) -> None:
        val = np.uint8(0)
        val |= np.uint8(clock_repeater) << np.uint8(0)
        val |= np.uint8(clock_generator) << np.uint8(1)
        val |= np.uint8(repeater_capability) << np.uint8(3)
        val |= np.uint8(generator_capability) << np.uint8(4)
        val |= np.uint8(clock_unlock) << np.uint8(6)
        val |= np.uint8(clock_lock) << np.uint8(7)
        self._arr = np.array([val], dtype=self._dtype)

    @property
    def clock_repeater(self) -> np.ndarray:
        return self._arr & np.uint8(0x01)

    @property
    def clock_generator(self) -> np.ndarray:
        return self._arr & np.uint8(0x02)

    @property
    def repeater_capability(self) -> np.ndarray:
        return self._arr & np.uint8(0x08)

    @property
    def generator_capability(self) -> np.ndarray:
        return self._arr & np.uint8(0x10)

    @property
    def clock_unlock(self) -> np.ndarray:
        return self._arr & np.uint8(0x40)

    @property
    def clock_lock(self) -> np.ndarray:
        return self._arr & np.uint8(0x80)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "clock_repeater": [self.clock_repeater],
                "clock_generator": [self.clock_generator],
                "repeater_capability": [self.repeater_capability],
                "generator_capability": [self.generator_capability],
                "clock_unlock": [self.clock_unlock],
                "clock_lock": [self.clock_lock],
            }
        )


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
