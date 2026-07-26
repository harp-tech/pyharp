from typing import Any, Mapping, Optional, Union

from ._device import Device
from ._register_map import REGISTER_MAP as CORE_REGISTER_MAP
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

    The returned class exposes its registers through ``REGISTER_MAP`` (address ->
    register class) and carries ``__whoami__`` from the schema (``0x0`` when
    absent). The device's registers are spread on top of the core common map; on
    an address clash the device's register wins. ``exclude_private=True`` drops
    registers whose DSL ``visibility`` is ``private``. A header-less register
    fragment yields a device with no ``device`` name (falls back to ``"Device"``).
    """
    device = source if isinstance(source, DeviceModel) else parse_device_schema(source)
    registers = create_registers(
        device, converters=converters, strict=strict, exclude_private=exclude_private
    )
    by_address = {cls.address: cls for cls in registers.values()}

    namespace: dict[str, Any] = {
        "__whoami__": int(device.whoAmI or 0),
        "REGISTER_MAP": {**CORE_REGISTER_MAP, **by_address},
    }
    return type(name or device.device or "Device", (Device,), namespace)
