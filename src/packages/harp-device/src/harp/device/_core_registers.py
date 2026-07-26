"""The common Harp registers as a tuple, plus a typed namespace for them.

Every :class:`~harp.device.Device` merges :data:`CORE_REGISTERS` with its own
``REGISTERS`` to build ``device.registers``. Statically generated devices subclass
:class:`CoreRegisters` to declare their device-specific registers with real types,
so ``device.registers.<Name>`` autocompletes and type-checks.
"""

from typing import Any

from harp.protocol import RegisterBase

from ._register_namespace import RegisterNamespace
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

#: The common Harp registers, present on every device.
CORE_REGISTERS: tuple[type[RegisterBase[Any]], ...] = (
    WhoAmI,
    HardwareVersionHigh,
    HardwareVersionLow,
    AssemblyVersion,
    CoreVersionHigh,
    CoreVersionLow,
    FirmwareVersionHigh,
    FirmwareVersionLow,
    TimestampSeconds,
    TimestampMicroseconds,
    OperationControl,
    ResetDevice,
    DeviceName,
    SerialNumber,
    ClockConfiguration,
)


class CoreRegisters(RegisterNamespace):
    """Typed register namespace declaring the common Harp registers.

    Every :class:`~harp.device.Device` exposes at least these as ``device.registers``.
    A statically generated device subclasses this to add its own registers with real
    types::

        class BehaviorRegisters(CoreRegisters):
            DigitalInputState: type[DigitalInputState]
            AnalogData: type[AnalogData]

    so ``device.registers.AnalogData`` autocompletes and type-checks. At runtime the
    namespace is populated from the device's registers; these annotations carry no
    runtime values.
    """

    WhoAmI: type[WhoAmI]
    HardwareVersionHigh: type[HardwareVersionHigh]
    HardwareVersionLow: type[HardwareVersionLow]
    AssemblyVersion: type[AssemblyVersion]
    CoreVersionHigh: type[CoreVersionHigh]
    CoreVersionLow: type[CoreVersionLow]
    FirmwareVersionHigh: type[FirmwareVersionHigh]
    FirmwareVersionLow: type[FirmwareVersionLow]
    TimestampSeconds: type[TimestampSeconds]
    TimestampMicroseconds: type[TimestampMicroseconds]
    OperationControl: type[OperationControl]
    ResetDevice: type[ResetDevice]
    DeviceName: type[DeviceName]
    SerialNumber: type[SerialNumber]
    ClockConfiguration: type[ClockConfiguration]
