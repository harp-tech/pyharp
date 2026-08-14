"""Address to register-class map for the core Harp registers.

Downstream device packages spread this into their own map::

    from harp.device.core import REGISTER_MAP as _CORE_REGISTER_MAP

    REGISTER_MAP = {**_CORE_REGISTER_MAP, 32: DigitalInputState, ...}
"""

from typing import Any

from harp.protocol import RegisterBase

from ._registers import (
    AssemblyVersion,
    ClockConfiguration,
    CoreVersionHigh,
    CoreVersionLow,
    DeviceName,
    FirmwareVersionHigh,
    FirmwareVersionLow,
    HardwareVersionHigh,
    HardwareVersionLow,
    OperationControl,
    ResetDevice,
    SerialNumber,
    TimestampMicroseconds,
    TimestampSeconds,
    WhoAmI,
)

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
