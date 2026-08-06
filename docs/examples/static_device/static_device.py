import enum
from typing import ClassVar

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


class ExampleRegisters(CoreRegisters):
    Encoder = Encoder
    Control = Control


# --- Device ------------------------------------------------------------------
class ExampleDevice(Device):
    """A statically defined Harp device.

    A subclass sets only `__whoami__` and `registers` — do not override the base's
    protocol methods.
    """

    __whoami__ = 1234
    # A mutable ClassVar is invariant, so pyright rejects narrowing it even though
    # `ExampleRegisters` is a `CoreRegisters`. The suppression is the cost of the
    # precise type on `device.registers.<Name>`.
    registers: ClassVar[ExampleRegisters] = ExampleRegisters()  # pyright: ignore[reportIncompatibleVariableOverride]


# Registers are reached by name, on the class or an instance:
assert ExampleDevice.registers.Encoder is Encoder
assert ExampleDevice.registers.Control.address == 33

# Use it exactly like a runtime-generated device (see the serial examples):
with open_serial_device(ExampleDevice, port="COM3") as device:
    print(device.read(device.registers.Encoder).parsed)  # by name
    print(device.read(Encoder).parsed)  # or the register class directly
