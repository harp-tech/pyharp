from typing import Any, Mapping, Optional, Union

from harp.protocol import RegisterBase

from ._core_registers import CORE_REGISTERS, CoreRegisters
from ._device import Device
from ._schema import create_registers, parse_device_schema
from ._schema._emit import ConverterValue
from ._schema._model import DeviceModel


def create_device(
    source: Union[str, DeviceModel],
    *,
    name: Optional[str] = None,
    converters: Optional[Mapping[str, ConverterValue]] = None,
    strict: bool = True,
    exclude_private: bool = True,
) -> type[Device]:
    """Emit a :class:`Device` subclass from a device schema.

    The returned class exposes the schema's registers, merged with the common Harp
    registers, by name through ``device.registers`` (e.g.
    ``Behavior.registers.AnalogData``).
    ``__whoami__`` comes from the schema (``0x0``
    when absent). On an address clash the device's register wins over the common one.
    ``exclude_private=True`` drops registers whose DSL ``visibility`` is ``private``.
    A header-less register fragment yields a device with no ``device`` name (falls
    back to ``"Device"``).
    """
    device = source if isinstance(source, DeviceModel) else parse_device_schema(source)
    registers = create_registers(
        device, converters=converters, strict=strict, exclude_private=exclude_private
    )

    merged: dict[int, type[RegisterBase[Any]]] = {reg.address: reg for reg in CORE_REGISTERS}
    for register in registers.values():
        merged[register.address] = register

    namespace: dict[str, Any] = {
        "__whoami__": int(device.whoAmI or 0),
        "registers": CoreRegisters.from_registers(merged.values()),
    }
    return type(name or device.device or "Device", (Device,), namespace)
