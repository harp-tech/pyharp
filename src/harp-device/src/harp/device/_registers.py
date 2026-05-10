import enum
from typing import ClassVar

import numpy as np
import pandas as pd
from harp.protocol._payload import PayloadBase, _BitFlag, _GroupMask
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

    operation_mode = _GroupMask(0x03, 0, OperationMode)
    dump_registers = _BitFlag(0x08)
    mute_replies = _BitFlag(0x10)
    visual_indicators = _GroupMask(0x20, 5, EnableFlag)
    operation_led = _GroupMask(0x40, 6, EnableFlag)
    heartbeat = _GroupMask(0x80, 7, EnableFlag)

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
        self._arr = np.array((val,), dtype=self._dtype)


class ResetDevicePayload(PayloadBase[np.uint8]):
    """Payload for the ResetDevice register (address 11)."""

    _dtype: ClassVar = np.dtype("u1")

    restore_default = _BitFlag(0x01)
    restore_eeprom = _BitFlag(0x02)
    save = _BitFlag(0x04)
    restore_name = _BitFlag(0x08)
    update_firmware = _BitFlag(0x20)
    boot_from_default = _BitFlag(0x40)
    boot_from_eeprom = _BitFlag(0x80)

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
        self._arr = np.array((val,), dtype=self._dtype)


class DeviceNamePayload(PayloadBase[np.uint8]):
    """Payload for the DeviceName register (address 12).

    Stores a user-specified ASCII device name padded to 25 bytes.
    Access the decoded string via ``.name``; ``.value`` returns the raw byte array.
    """

    _MAX_LEN: ClassVar[int] = 25
    _dtype: ClassVar = np.dtype([("value", "u1", (_MAX_LEN,))])
    _repr_fields: ClassVar = ("name",)

    def __init__(self, name: str) -> None:
        encoded = name.encode("ascii")[: self._MAX_LEN]
        padded = encoded.ljust(self._MAX_LEN, b"\x00")
        arr = np.zeros((), dtype=self._dtype)
        arr["value"] = np.frombuffer(padded, dtype="u1")
        self._arr = arr

    @property
    def name(self) -> str:
        # 0-D _arr (parse / __init__): _arr["value"] is shape (_MAX_LEN,).
        # 1-D _arr (batch): take row 0 — Batch users should iterate rows
        # explicitly via _arr["value"] if they need every name.
        raw = self._arr["value"] if self._arr.ndim == 0 else self._arr["value"][0]
        return raw.tobytes().rstrip(b"\x00").decode("ascii")

    def to_dataframe(self) -> pd.DataFrame:
        if self._arr.ndim == 0:
            return pd.DataFrame({"name": [self.name]})
        names = [row.tobytes().rstrip(b"\x00").decode("ascii") for row in self._arr["value"]]
        return pd.DataFrame({"name": names})


class ClockConfigPayload(PayloadBase[np.uint8]):
    """Payload for the ClockConfiguration register (address 14)."""

    _dtype: ClassVar = np.dtype("u1")

    clock_repeater = _BitFlag(0x01)
    clock_generator = _BitFlag(0x02)
    repeater_capability = _BitFlag(0x08)
    generator_capability = _BitFlag(0x10)
    clock_unlock = _BitFlag(0x40)
    clock_lock = _BitFlag(0x80)

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
        self._arr = np.array((val,), dtype=self._dtype)


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
