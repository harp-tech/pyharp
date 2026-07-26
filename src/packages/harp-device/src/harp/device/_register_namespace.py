"""A name-indexed view over a device's register classes.

`Device.registers` is a :class:`RegisterNamespace`, so registers are reached by
name — ``device.registers.WhoAmI`` — with the ``by_name`` / ``by_address`` maps for
programmatic lookup. Statically generated devices narrow the type to a
:class:`CoreRegisters` subclass so editors autocomplete the register names; see
:class:`CoreRegisters`.
"""

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from harp.protocol import RegisterBase

_Register = type[RegisterBase[Any]]


class RegisterNamespace:
    """Attribute-addressable collection of register classes.

    Built from an iterable of register classes; each is indexed by its
    ``__name__`` and its ``address``. Registers are reached by name::

        ns = RegisterNamespace([WhoAmI, OperationControl])
        ns.WhoAmI          # -> type[WhoAmI]  (attribute access)
        ns.by_name         # {"WhoAmI": WhoAmI, "OperationControl": OperationControl}
        ns.by_address      # {0: WhoAmI, 10: OperationControl}

    Iteration yields the register classes, and ``in`` tests register-class
    membership (``WhoAmI in ns``). Attribute access falls back to
    :meth:`__getattr__`, typed as ``type[RegisterBase[Any]]`` so any register name
    type-checks; a :class:`CoreRegisters` subclass declares specific names for
    precise types.
    """

    def __init__(self, registers: Iterable[_Register]) -> None:
        self._registers = tuple(registers)
        self._by_name = {register.__name__: register for register in self._registers}
        self._by_address = {register.address: register for register in self._registers}

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
