"""A name-indexed view over a device's register classes.

`Device.registers` is a :class:`RegisterMap`, so registers are reached by
name — ``device.registers.WhoAmI`` — with the ``by_name`` / ``by_address`` maps for
programmatic lookup. Statically generated devices narrow the type to a
:class:`~harp.device.CoreRegisters` subclass so editors autocomplete the register
names; see :class:`~harp.device.CoreRegisters` (which itself is a
:class:`RegisterMap`).
"""

from collections.abc import Iterable, Iterator, Mapping
from types import MappingProxyType
from typing import Any, Self

from harp.protocol import RegisterBase

_Register = type[RegisterBase[Any]]


class RegisterMap:
    """Attribute-addressable collection of register classes.

    A subclass **declares** its registers as class attributes; instantiating it
    introspects the class and indexes each one by its ``__name__`` and its
    ``address``::

        class MyRegisters(RegisterMap):
            WhoAmI = WhoAmI
            OperationControl = OperationControl

        ns = MyRegisters()
        ns.WhoAmI          # -> type[WhoAmI]  (autocompletes and type-checks)
        ns.by_name         # {"WhoAmI": WhoAmI, "OperationControl": OperationControl}
        ns.by_address      # {0: WhoAmI, 10: OperationControl}

    Declaring them as assignments rather than ``WhoAmI: type[WhoAmI]`` annotations
    is what makes this work: a bare annotation carries no runtime value, so there
    would be nothing to introspect. Static typing is unaffected — each member is
    still inferred as ``type[<Register>]``.

    :meth:`from_registers` builds the same map from an iterable instead, for
    dynamically generated devices whose register set isn't known at author time.

    Iteration yields the register classes, and ``in`` tests register-class
    membership (``WhoAmI in ns``). Attribute access falls back to
    :meth:`__getattr__`, typed as ``type[RegisterBase[Any]]``, so a register that
    only exists at runtime still type-checks.
    """

    _by_name: Mapping[str, _Register]
    _by_address: Mapping[int, _Register]

    def __init__(self) -> None:
        self._registers = tuple(self._resolve_register_map())
        self._resolve_mappings()

    @classmethod
    def from_registers(cls, registers: Iterable[_Register]) -> Self:
        """Construct a :class:`RegisterMap` from an iterable of register classes.
        Useful for dynamically generated devices that don't have a static register list."""
        instance = cls.__new__(cls)
        instance._registers = tuple(registers)
        instance._resolve_mappings()
        return instance

    def _resolve_mappings(self) -> None:
        """Resolve the name and address mappings from the register list."""
        # MappingProxyType makes the maps read-only, so they can't be accidentally
        # mutated at runtime.
        self._by_name = MappingProxyType({reg.__name__: reg for reg in self._registers})
        self._by_address = MappingProxyType({reg.address: reg for reg in self._registers})

    @classmethod
    def _resolve_register_map(cls) -> Iterator[_Register]:
        """Yield every register class declared as an attribute on ``cls`` or its bases."""
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(cls, attr_name)
            if isinstance(attr, type) and issubclass(attr, RegisterBase):
                yield attr

    def __getattr__(self, name: str) -> _Register:
        # Only consulted when normal attribute lookup fails, so real methods and
        # the ``_registers``/``_by_*`` internals always win. Guard dunder/private
        # lookups so a missing ``_by_name`` (e.g. during copy/pickle) can't recurse.
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self.__dict__["_by_name"][name]
        except KeyError:
            raise AttributeError(
                f"no register named {name!r}; available: {', '.join(self.__dict__['_by_name'])}"
            ) from None

    @property
    def by_name(self) -> Mapping[str, _Register]:
        """The name -> register-class map."""
        return self._by_name

    @property
    def by_address(self) -> Mapping[int, _Register]:
        """The address -> register-class map."""
        return self._by_address

    def __iter__(self) -> Iterator[_Register]:
        return iter(self._registers)

    def __contains__(self, register: object) -> bool:
        return any(register is r for r in self._registers)

    def __len__(self) -> int:
        return len(self._registers)

    def __dir__(self) -> Iterable[str]:
        return [*super().__dir__(), *self._by_name]

    def __repr__(self) -> str:
        names = ", ".join(sorted(self._by_name))
        return f"{type(self).__name__}({names})"
