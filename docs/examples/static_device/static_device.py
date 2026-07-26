import enum
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from harp.device import CoreRegisters, Device
from harp.protocol import (
    BoolConverter,
    Field,
    GroupMask,
    PayloadType,
    RegisterBase,
    RegisterU16,
    StructPayload,
)
from harp.serial import open_serial_device

# A statically defined device: plain Python classes, no schema or runtime
# generation. This is what you write by hand for a distributable, fully typed
# device package — and exactly what a code generator emits from a `device.yml`.


# --- Enums -------------------------------------------------------------------
class LedMode(enum.IntEnum):
    """Values for the Control register's `led` field."""

    OFF = 0
    ON = 1
    BLINK = 2


# --- Register payloads -------------------------------------------------------
class ControlPayload(StructPayload[np.uint8]):
    """Payload of the Control register: a masked enum plus a boolean flag."""

    led: LedMode = GroupMask(enum=LedMode, mask=0x3)
    enabled: bool = Field(BoolConverter(), mask=0x4)


# --- Registers ---------------------------------------------------------------
# Each register is a `RegisterBase` subclass carrying its `address`. Scalars can
# use the `Register<Type>` shortcuts; structured registers point at a payload class.
class Encoder(RegisterU16):
    """A 16-bit counter — a plain scalar register."""

    address: ClassVar[int] = 32


class Control(RegisterBase[ControlPayload]):
    """A structured register decoded through `ControlPayload`."""

    address: ClassVar[int] = 33
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ControlPayload


# --- Device ------------------------------------------------------------------
class ExampleDevice(Device):
    """A statically defined Harp device.

    A subclass sets only `__whoami__` and `__REGISTERS__`. The common Harp
    registers are merged in and `device.registers` is derived automatically — do
    not declare a `REGISTER_MAP` or override the base's protocol methods.
    """

    __whoami__ = 1234
    __REGISTERS__ = (Encoder, Control)

    if TYPE_CHECKING:
        # Optional but recommended: makes `device.registers.<Name>` autocomplete and
        # type precisely. It deliberately narrows the base `registers` attribute, so
        # the override warning is silenced. Carries no runtime values.
        class _Registers(CoreRegisters):
            Encoder: type[Encoder]
            Control: type[Control]

        registers: ClassVar[_Registers]  # pyright: ignore[reportIncompatibleVariableOverride]


# Registers are reached by name, on the class or an instance:
assert ExampleDevice.registers.Encoder is Encoder
assert ExampleDevice.registers.Control.address == 33

# Use it exactly like a runtime-generated device (see the serial examples):
with open_serial_device(ExampleDevice, port="COM3") as device:
    print(device.read(device.registers.Encoder).parsed)  # by name
    print(device.read(Encoder).parsed)  # or the register class directly
