import enum
from typing import ClassVar

import numpy as np
import pandas as pd
from harp.protocol._payload import PayloadBase
from harp.protocol._payload_type import PayloadType
from harp.protocol._register import RegisterBase, RegisterU8, RegisterU16, RegisterU32
from numpy.typing import NDArray


class OperationMode(enum.IntEnum):
    Standby = 0
    Active = 1
    Speed = 2
    Reserved = 3


class OperationControlPayload(PayloadBase[np.void]):
    _dtype: ClassVar = np.dtype([("operation_control", "u1")])
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
        operation_mode: int | np.uint8 = 0,
        dump_registers: bool = False,
        mute_replies: bool = False,
        visual_indicators: int | np.uint8 = 0,
        operation_led: int | np.uint8 = 0,
        heartbeat: int | np.uint8 = 0,
    ) -> None:
        arr = np.zeros(1, dtype=self._dtype)
        arr["operation_control"] |= np.uint8(operation_mode) & 0x03
        arr["operation_control"] |= np.uint8(dump_registers) << 3
        arr["operation_control"] |= np.uint8(mute_replies) << 4
        arr["operation_control"] |= (np.uint8(visual_indicators) & 0x01) << 5
        arr["operation_control"] |= (np.uint8(operation_led) & 0x01) << 6
        arr["operation_control"] |= (np.uint8(heartbeat) & 0x01) << 7
        self._arr = arr

    @property
    def operation_mode(self) -> NDArray[np.uint8]:
        return self._arr["operation_control"] & np.uint8(0x03)

    @property
    def dump_registers(self) -> NDArray[np.bool_]:
        return (self._arr["operation_control"] & np.uint8(0x08)) != 0

    @property
    def mute_replies(self) -> NDArray[np.bool_]:
        return (self._arr["operation_control"] & np.uint8(0x10)) != 0

    @property
    def visual_indicators(self) -> NDArray[np.bool_]:
        return ((self._arr["operation_control"] >> 5) & np.uint8(0x01)) != 0

    @property
    def operation_led(self) -> NDArray[np.bool_]:
        return ((self._arr["operation_control"] >> 6) & np.uint8(0x01)) != 0

    @property
    def heartbeat(self) -> NDArray[np.bool_]:
        return ((self._arr["operation_control"] >> 7) & np.uint8(0x01)) != 0

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "operation_mode": self.operation_mode,
                "dump_registers": self.dump_registers,
                "mute_replies": self.mute_replies,
                "visual_indicators": self.visual_indicators,
                "operation_led": self.operation_led,
                "heartbeat": self.heartbeat,
            }
        )


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


class ResetDevice(RegisterU8):
    address: ClassVar[int] = 11


class ClockConfig(RegisterU8):
    address: ClassVar[int] = 14


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
    address: ClassVar[int] = 15
    address: ClassVar[int] = 15
