"""Static conformance checks for the documented public API.

Nothing here runs. Every function is a type-checker fixture, asserting the type a
documented expression resolves to, so a change that silently degrades an inferred
type fails the build rather than being noticed downstream.
"""

from typing import Any, assert_type

import numpy as np
from harp.data import DatasetReader
from harp.device import (
    Device,
    DeviceModule,
    DeviceModuleLike,
    OperationControl,
    OperationControlPayload,
    WhoAmI,
    create_device_module,
)
from harp.protocol import ParsedHarpMessage, RegisterBase


def schema_built_registers(yml: str) -> None:
    """A module built from a schema types its registers collectively."""
    behavior = create_device_module(yml)
    assert_type(behavior, DeviceModule)
    assert_type(behavior.AnalogData, type[RegisterBase[Any]])
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


def dataset_reader_accepts_either_module(
    schema_built: DeviceModule, generated: DeviceModuleLike
) -> None:
    """The reader takes a schema-built module and a generated package alike."""
    DatasetReader(schema_built, "session.harp")
    reader = DatasetReader(generated, "session.harp")
    reader.read(WhoAmI)
    reader.read(44)
