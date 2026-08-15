"""Static conformance checks for the documented public API.

Nothing here runs. Every function is a type-checker fixture, asserting the type a
documented expression resolves to, so a change that silently degrades an inferred
type fails the build rather than being noticed downstream.
"""

from typing import Any, ClassVar, assert_type

import numpy as np
from harp.data import DatasetReader
from harp.device.client import Device, ITransport
from harp.device.core import OperationControl, OperationControlPayload, WhoAmI
from harp.device.schema import DeviceModule, DeviceModuleLike, create_device_module
from harp.protocol import ParsedHarpMessage, RegisterBase
from harp.serial import open_serial_device


def schema_built_registers(yml: str) -> None:
    """A module built from a schema types its registers collectively."""
    behavior = create_device_module(yml)
    assert_type(behavior, DeviceModule)
    assert_type(behavior.AnalogData, Any)
    assert_type(behavior.REGISTER_MAP, dict[int, type[RegisterBase[Any]]])
    assert_type(behavior.WHO_AM_I, int)


def statically_declared_registers(device: Device) -> None:
    """A register written out in a module carries its payload type through read."""
    assert_type(device.read(WhoAmI), ParsedHarpMessage[np.uint16])
    assert_type(device.read(WhoAmI).parsed, np.uint16)
    assert_type(device.read(OperationControl).parsed, OperationControlPayload)


def register_writes(device: Device, payload: OperationControlPayload) -> None:
    """Write accepts the payload type its register parses to."""
    assert_type(device.write(OperationControl, payload).parsed, OperationControlPayload)


def device_with_module(transport: ITransport, module: DeviceModule) -> None:
    """Device constructed with a module is typed on that module."""
    device = Device(transport, module)
    assert_type(device, Device[DeviceModule])
    assert_type(device.module, DeviceModule)


def device_without_module(transport: ITransport) -> None:
    """Device constructed without a module is Device[None]."""
    device = Device(transport)
    assert_type(device, Device[None])
    assert_type(device.module, None)


def open_serial_device_with_module(module: DeviceModule) -> None:
    """open_serial_device with a module returns Device[M]."""
    device = open_serial_device(module, port="COM3")
    assert_type(device, Device[DeviceModule])
    assert_type(device.module, DeviceModule)


def open_serial_device_without_module() -> None:
    """open_serial_device without a module returns Device[None]."""
    device = open_serial_device(port="COM3")
    assert_type(device, Device[None])
    assert_type(device.module, None)


def open_serial_device_with_subclass() -> None:
    """open_serial_device with a Device subclass preserves its type."""

    class MyDevice(Device[DeviceModule]):
        def arm(self) -> None: ...

    device = open_serial_device(MyDevice, port="COM3")
    assert_type(device, MyDevice)


def dataset_reader_accepts_either_module(
    schema_built: DeviceModule, generated: DeviceModuleLike
) -> None:
    """The reader takes a schema-built module and a generated package alike."""
    DatasetReader(schema_built, "session.harp")
    reader = DatasetReader(generated, "session.harp")
    reader.read(WhoAmI)
    reader.read(44)


def open_serial_device_prefers_the_subclass_overload() -> None:
    """A Device subclass is matched as a subclass even when it looks like a module.

    type[D] is narrower than the structural module overload, so it has to come first:
    a class carrying REGISTER_MAP and WHO_AM_I satisfies DeviceModuleLike too, and the
    module overload would otherwise win and return Device[type[Hybrid]].
    """

    class Hybrid(Device[None]):
        REGISTER_MAP: ClassVar[dict[int, type[RegisterBase[Any]]]] = {}
        WHO_AM_I: ClassVar[int] = 1216

    device = open_serial_device(Hybrid, port="COM3")
    assert_type(device, Hybrid)
