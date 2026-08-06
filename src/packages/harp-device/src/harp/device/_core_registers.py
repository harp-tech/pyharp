"""The common Harp registers as a tuple, plus a typed namespace for them.

Every :class:`~harp.device.Device` merges :data:`CORE_REGISTERS` with its own
``REGISTERS`` to build ``device.registers``. Statically generated devices subclass
:class:`CoreRegisters` to declare their device-specific registers with real types,
so ``device.registers.<Name>`` autocompletes and type-checks.
"""

from typing import Any

from harp.protocol import RegisterBase

from ._register_namespace import RegisterMap
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


class CoreRegisters(RegisterMap):
    """Typed register namespace declaring the common Harp registers.

    Every :class:`~harp.device.Device` exposes at least these as ``device.registers``.
    A statically generated device subclasses this to add its own registers::

        class BehaviorRegisters(CoreRegisters):
            DigitalInputState = DigitalInputState
            AnalogData = AnalogData

    so ``device.registers.AnalogData`` autocompletes and type-checks (each member is
    inferred as ``type[<Register>]``, exactly as a ``: type[...]`` annotation would
    be). These are **assignments**, not annotations, because
    :class:`~harp.device.RegisterMap` introspects the class for real attribute values
    to build its name and address maps — a bare annotation carries none.
    """

    WhoAmI = WhoAmI
    HardwareVersionHigh = HardwareVersionHigh
    HardwareVersionLow = HardwareVersionLow
    AssemblyVersion = AssemblyVersion
    CoreVersionHigh = CoreVersionHigh
    CoreVersionLow = CoreVersionLow
    FirmwareVersionHigh = FirmwareVersionHigh
    FirmwareVersionLow = FirmwareVersionLow
    TimestampSeconds = TimestampSeconds
    TimestampMicroseconds = TimestampMicroseconds
    OperationControl = OperationControl
    ResetDevice = ResetDevice
    DeviceName = DeviceName
    SerialNumber = SerialNumber
    ClockConfiguration = ClockConfiguration
