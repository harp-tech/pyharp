from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

import numpy as np
from numpy.typing import NDArray

T = TypeVar("T")
NpScalarT = TypeVar("NpScalarT", bound=np.generic)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

converter_registry: "dict[str, type[Converter[Any]]]" = {}


def register_converter(*, name: str) -> "Callable[[type[Converter[Any]]], type[Converter[Any]]]":
    """Class decorator that registers a ``Converter`` subclass under ``name``.

    Raises ``ValueError`` if the name is already registered.

    Usage::

        @register_converter(name="my_converter")
        class MyConverter(Converter[int]): ...
    """

    def _register(cls: "type[Converter[Any]]") -> "type[Converter[Any]]":
        if name in converter_registry:
            raise ValueError(
                f"A converter named {name!r} is already registered "
                f"(existing: {converter_registry[name]!r}, new: {cls!r})"
            )
        converter_registry[name] = cls
        return cls

    return _register


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Converter(ABC, Generic[T]):
    """Abstract base for payload field converters.

    Subclasses must set ``dtype`` and ``init_kwarg_type`` as class attributes
    and implement the three abstract methods.
    """

    dtype: np.dtype  # dtype of the raw numpy slot passed to decode/encode
    init_kwarg_type: type  # used for docs/introspection; not enforced at runtime

    @abstractmethod
    def decode_scalar(self, view: np.generic) -> T:
        """Decode a 0-D structured-array element into a Python value."""

    @abstractmethod
    def decode_batch(self, view: "NDArray[np.generic]") -> Any:
        """Decode a 1-D structured-array column into an array-like."""

    @abstractmethod
    def encode_into(self, view: NDArray[np.generic], value: T) -> None:
        """Write a Python value back into a structured-array element."""


# ---------------------------------------------------------------------------
# Built-in converters
# ---------------------------------------------------------------------------


class IdentityConverter(Converter[NpScalarT]):
    """Pass-through converter — the raw numpy scalar is returned as-is."""

    def __init__(self, dtype: "np.dtype[NpScalarT] | str | type[NpScalarT]") -> None:
        self.dtype = np.dtype(dtype)
        self.init_kwarg_type = self.dtype.type

    def decode_scalar(self, view: np.generic) -> NpScalarT:
        return cast(
            NpScalarT, view
        )  # this should be safe since dtype is scalar and matches the type var

    def decode_batch(self, view: NDArray[np.generic]) -> "NDArray[NpScalarT]":
        return cast("NDArray[NpScalarT]", view)

    def encode_into(self, view: NDArray[np.generic], value: NpScalarT) -> None:
        view[...] = value


@register_converter(name="String")  # TODO check this name against Bonsai
class StringConverter(Converter[str]):
    """Converts a fixed-length byte array to/from a Python ``str``."""

    init_kwarg_type = str

    def __init__(self, length: int, encoding: str = "ascii") -> None:
        self._length = length
        self._encoding = encoding
        self.dtype = np.dtype((np.uint8, (length,)))

    def decode_scalar(self, view: np.generic) -> str:
        return bytes(view).rstrip(b"\x00").decode(self._encoding)

    def decode_batch(self, view: NDArray[np.generic]) -> Any:
        return np.array(
            [bytes(row).rstrip(b"\x00").decode(self._encoding) for row in view],
            dtype=object,
        )

    def encode_into(self, view: NDArray[np.generic], value: str) -> None:
        encoded = value.encode(self._encoding)[: self._length]
        padded = encoded.ljust(self._length, b"\x00")
        view[...] = np.frombuffer(padded, dtype=np.uint8)
