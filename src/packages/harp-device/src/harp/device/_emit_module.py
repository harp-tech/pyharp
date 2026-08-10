"""Emit a Python module of register classes from a device schema.

A generated device package is already a module: register classes at module level
and a ``REGISTER_MAP`` beside them (see the ``harp-device`` README).
:func:`create_device_module` builds that same shape at runtime from a ``device.yml``, so a
schema-driven device and a generated one are reached the same way, by name from the
module or by address through ``REGISTER_MAP``.
"""

import types
from typing import Any, Mapping, Optional, Protocol, Union, runtime_checkable

from harp.protocol import RegisterBase

from ._register_map import REGISTER_MAP as CORE_REGISTER_MAP
from ._schema import create_registers, parse_device_schema
from ._schema._emit import ConverterValue
from ._schema._model import DeviceModel

#: Module name used when the schema carries no ``device`` header.
_DEFAULT_NAME = "Device"


@runtime_checkable
class DeviceModuleLike(Protocol):
    """Any module describing a device, however it was produced.

    A generated device package is a plain module, so it cannot be named by a class;
    what identifies it is carrying the register map. Matching structurally accepts
    both it and :class:`DeviceModule`, and rejects a module that follows neither.
    """

    __name__: str
    REGISTER_MAP: dict[int, type[RegisterBase[Any]]]


class DeviceModule(types.ModuleType):
    """The module :func:`create_device_module` returns, describing what a device module holds.

    Declaring the members is what lets a linter resolve them. Register names come
    from the schema, so they can only be described collectively, through
    :meth:`__getattr__`; ``REGISTER_MAP`` and ``WHO_AM_I`` are named and keep their
    own types. A statically generated device package is a plain module and needs
    none of this, since its registers are written out.
    """

    #: Address -> register class, the common Harp registers merged with the schema's.
    REGISTER_MAP: dict[int, type[RegisterBase[Any]]]
    #: The device identity declared by the schema; ``0`` when absent.
    WHO_AM_I: int

    def __getattr__(self, name: str) -> type[RegisterBase[Any]]:
        raise AttributeError(f"module {self.__name__!r} has no register named {name!r}")


def create_device_module(
    source: Union[str, DeviceModel],
    *,
    name: Optional[str] = None,
    converters: Optional[Mapping[str, ConverterValue]] = None,
    strict: bool = True,
    exclude_private: bool = True,
) -> DeviceModule:
    """Emit a module of register classes from a device schema.

    The module holds the schema's registers merged with the common Harp registers,
    each reachable by name (``behavior.AnalogData``), plus:

    * ``REGISTER_MAP``, the address -> register-class map;
    * ``WHO_AM_I``, the schema's identity (``0`` when absent);
    * ``__name__``, the schema's ``device`` name, or ``name`` when given
      (``"Device"`` for a header-less register fragment).

    Because the names come from the schema at runtime they don't autocomplete, and
    each resolves as ``type[RegisterBase[Any]]`` rather than its own register type;
    a generated device package is a real module on disk and gives both. On a
    collision the device's register wins over the common one.
    ``exclude_private=True`` drops registers whose DSL ``visibility`` is ``private``.

    The module is **not** registered in :data:`sys.modules`, so it cannot be reached
    by ``import`` and two schemas may share a name without clashing. Bind it
    yourself::

        behavior = create_device_module(Path("device.yml").read_text())
        behavior.AnalogData
    """
    device = source if isinstance(source, DeviceModel) else parse_device_schema(source)
    registers = create_registers(
        device, converters=converters, strict=strict, exclude_private=exclude_private
    )
    module_name = name or device.device or _DEFAULT_NAME

    claimed = {cls.address for cls in registers.values()}
    contents: dict[str, type[RegisterBase[Any]]] = {
        cls.__name__: cls
        for cls in CORE_REGISTER_MAP.values()
        if cls.address not in claimed and cls.__name__ not in registers
    }
    contents.update(registers)

    for register in registers.values():
        register.__module__ = module_name

    module = DeviceModule(module_name, f"Harp registers for {module_name}, from a schema.")
    vars(module).update(
        contents,
        REGISTER_MAP={cls.address: cls for cls in contents.values()},
        WHO_AM_I=int(device.whoAmI or 0),
        __all__=[*sorted(contents), "REGISTER_MAP", "WHO_AM_I"],
    )
    return module
