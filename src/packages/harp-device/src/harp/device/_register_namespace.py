"""A name/address-indexed view over a device's register classes.

`Device.registers` is a :class:`RegisterNamespace`, so registers are reached by
name — ``device.registers.WhoAmI`` — as well as by address
(``device.registers[0]`` / ``device.registers.by_address``). Statically generated
devices narrow the type to a :class:`CoreRegisters` subclass so editors autocomplete
the register names; see :class:`CoreRegisters`.
"""

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from harp.protocol import RegisterBase

_Register = type[RegisterBase[Any]]


class RegisterNamespace:
    """Attribute- and item-addressable collection of register classes.

    Built from an iterable of register classes; each is indexed by its
    ``__name__`` and its ``address``. Attribute access returns the register class::

        ns = RegisterNamespace([WhoAmI, OperationControl])
        ns.WhoAmI          # -> type[WhoAmI]
        ns["WhoAmI"]       # -> type[WhoAmI]  (by name)
        ns[0]              # -> type[WhoAmI]  (by address)
        ns.by_address      # {0: WhoAmI, 10: OperationControl}

    Attribute access falls back to :meth:`__getattr__`, typed as
    ``type[RegisterBase[Any]]`` so any register name type-checks; a
    :class:`CoreRegisters` subclass declares specific names for precise types.
    """

    def __init__(self, registers: Iterable[_Register]) -> None:
        by_name: dict[str, _Register] = {}
        by_address: dict[int, _Register] = {}
        for register in registers:
            by_name[register.__name__] = register
            by_address[register.address] = register
        self._by_name = by_name
        self._by_address = by_address

    def __getattr__(self, name: str) -> _Register:
        # Only consulted when normal attribute lookup fails, so real methods and
        # the ``_by_*`` internals always win. Guard dunder/private lookups so a
        # missing ``_by_name`` (e.g. during copy/pickle) can't recurse.
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self.__dict__["_by_name"][name]
        except KeyError:
            raise AttributeError(
                f"no register named {name!r}; available: {', '.join(self.__dict__['_by_name'])}"
            ) from None

    def __getitem__(self, key: str | int) -> _Register:
        try:
            if isinstance(key, int):
                return self._by_address[key]
            return self._by_name[key]
        except KeyError:
            kind = "address" if isinstance(key, int) else "name"
            raise KeyError(f"no register with {kind} {key!r}") from None

    @property
    def by_name(self) -> Mapping[str, _Register]:
        """The name -> register-class map."""
        return self._by_name

    @property
    def by_address(self) -> Mapping[int, _Register]:
        """The address -> register-class map."""
        return self._by_address

    def __iter__(self) -> Iterator[_Register]:
        return iter(self._by_name.values())

    def __contains__(self, key: object) -> bool:
        if isinstance(key, int):
            return key in self._by_address
        if isinstance(key, str):
            return key in self._by_name
        return key in self._by_name.values()

    def __len__(self) -> int:
        return len(self._by_name)

    def __dir__(self) -> Iterable[str]:
        return [*super().__dir__(), *self._by_name]

    def __repr__(self) -> str:
        names = ", ".join(sorted(self._by_name))
        return f"{type(self).__name__}({names})"
