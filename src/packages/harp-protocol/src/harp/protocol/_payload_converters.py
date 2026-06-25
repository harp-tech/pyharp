import enum as _enum
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, cast
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray

T = TypeVar("T")
NpScalarT = TypeVar("NpScalarT", bound=np.generic)
E = TypeVar("E", bound=_enum.IntEnum)

# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class Converter(ABC, Generic[T]):
    """Abstract base for payload field converters.

    Subclasses must set ``dtype`` and ``init_kwarg_type`` as class attributes
    and implement the three abstract methods.
    """

    dtype: np.dtype  # dtype of the raw numpy slot passed to decode/encode
    init_kwarg_type: type  # used for docs/introspection TODO especially to generate the constructor type hints; not enforced at runtime

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


class UInt8Converter(IdentityConverter[np.uint8]):
    def __init__(self) -> None:
        super().__init__(np.uint8)


class SInt8Converter(IdentityConverter[np.int8]):
    def __init__(self) -> None:
        super().__init__(np.int8)


class UInt16Converter(IdentityConverter[np.uint16]):
    def __init__(self) -> None:
        super().__init__(np.uint16)


class Int16Converter(IdentityConverter[np.int16]):
    def __init__(self) -> None:
        super().__init__(np.int16)


class UInt32Converter(IdentityConverter[np.uint32]):
    def __init__(self) -> None:
        super().__init__(np.uint32)


class Int32Converter(IdentityConverter[np.int32]):
    def __init__(self) -> None:
        super().__init__(np.int32)


class UInt64Converter(IdentityConverter[np.uint64]):
    def __init__(self) -> None:
        super().__init__(np.uint64)


class Int64Converter(IdentityConverter[np.int64]):
    def __init__(self) -> None:
        super().__init__(np.int64)


class FloatConverter(IdentityConverter[np.float32]):
    def __init__(self) -> None:
        super().__init__(np.float32)


class BoolConverter(Converter[bool]):
    """Whole-element ``interfaceType: bool`` (distinct from a single ``BitFlag`` bit).

    The element is non-zero → ``True``. Operates on a single base element.
    """

    init_kwarg_type = bool

    def __init__(self, dtype: "np.dtype | str | type" = np.uint8) -> None:
        self.dtype = np.dtype(dtype)

    def decode_scalar(self, view: np.generic) -> bool:
        return bool(view)

    def decode_batch(self, view: NDArray[np.generic]) -> Any:
        return np.asarray(view) != 0

    def encode_into(self, view: NDArray[np.generic], value: bool) -> None:
        view[...] = 1 if value else 0


class EnumConverter(Converter[E]):
    """Whole-element ``interfaceType: <maskType>`` enum (strict).

    Maps a base element to an ``enum.IntEnum`` member; an unknown code raises
    ``ValueError`` (matching Python ``IntEnum`` semantics). For masked enum
    sub-fields use :class:`~harp.protocol.GroupMask` with ``enum=`` instead.
    """

    def __init__(self, enum_cls: "type[E]", dtype: "np.dtype | str | type" = np.uint8) -> None:
        self._enum = enum_cls
        self.dtype = np.dtype(dtype)
        self.init_kwarg_type = enum_cls

    def decode_scalar(self, view: np.generic) -> E:
        return self._enum(int(view))

    def decode_batch(self, view: NDArray[np.generic]) -> Any:
        return np.asarray(view)

    def encode_into(self, view: NDArray[np.generic], value: E) -> None:
        view[...] = int(value)


class StringConverter(Converter[str]):
    """Converts a fixed-length byte array to/from a Python ``str``."""

    def __init__(self, length: int, encoding: str = "ascii") -> None:
        self._length = length
        self._encoding = encoding
        self.dtype = np.dtype((np.uint8, (length,)))

    def decode_scalar(self, view: np.generic) -> str:
        return bytes(view).rstrip(b"\x00").decode(self._encoding)  # ty: ignore[invalid-argument-type]

    def decode_batch(self, view: NDArray[np.generic]) -> Any:
        return np.array(
            [bytes(row).rstrip(b"\x00").decode(self._encoding) for row in view],
            dtype=object,
        )

    def encode_into(self, view: NDArray[np.generic], value: str) -> None:
        encoded = value.encode(self._encoding)[: self._length]
        padded = encoded.ljust(self._length, b"\x00")
        view[...] = np.frombuffer(padded, dtype=np.uint8)


@dataclass(frozen=True)
class HarpVersion:
    """Represents a Harp version"""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


class HarpVersionConverter(Converter[HarpVersion]):
    """Converts a 3-element uint8 array to/from a HarpVersion object."""

    init_kwarg_type = HarpVersion

    def __init__(self, component: "np.dtype | str | type" = np.uint8) -> None:
        self.dtype = np.dtype((component, (3,)))

    def decode_scalar(self, view: np.generic) -> HarpVersion:
        c = np.asarray(view).tolist()
        return HarpVersion(int(c[0]), int(c[1]), int(c[2]))

    def decode_batch(self, view: NDArray[np.generic]) -> Any:
        return np.array(
            [HarpVersion(int(r[0]), int(r[1]), int(r[2])) for r in np.atleast_2d(view)],
            dtype=object,
        )

    def encode_into(self, view: NDArray[np.generic], value: HarpVersion) -> None:
        view[...] = np.array([value.major, value.minor, value.patch], dtype=self.dtype.base)
