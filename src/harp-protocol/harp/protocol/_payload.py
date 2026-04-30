from __future__ import annotations

from typing import ClassVar, Generic, Self, TypeVar, final

import numpy as np
import pandas as pd
from numpy.typing import NDArray

NpStructT = TypeVar("NpStructT", bound=np.generic)

class PayloadBase(Generic[NpStructT]):
    """Base class for typed Harp register payloads.

    Subclasses define ``_dtype: ClassVar[np.dtype]`` for the register layout::

        class AnalogDataPayload(PayloadBase):
            _dtype: ClassVar = np.dtype([
                ("analog_input0", "<i2"),
                ("encoder", "<i2"),
            ])

    The type parameter ``NpStructT`` is the numpy scalar type that corresponds
    to ``_dtype`` at the type-checker level.  For scalar dtypes the two are
    equivalent — ``np.dtype("<u4").type is np.uint32`` — so a scalar subclass
    should declare both together::

        class PayloadU32(PayloadBase[np.uint32]):
            _dtype: ClassVar = np.dtype("<u4")

    For structured dtypes use ``np.void``::

        class AnalogDataPayload(PayloadBase[np.void]):
            _dtype: ClassVar = np.dtype([("analog_input0", "<i2"), ...])

    ``NpStructT`` is a runtime-invisible type-checker hint; it only affects the
    inferred type of ``value`` and ``raw_payload``.  ``_dtype`` is the runtime
    source of truth used for all array construction and field access.

    To customise the string representation, set ``_repr_fields`` to a tuple of
    property (or attribute) names that should appear in ``repr``/``str``.  When
    not set the base class falls back to the dtype field names for structured
    dtypes, or ``"value"`` for scalar dtypes.
    """

    _dtype: ClassVar[np.dtype]
    _repr_fields: ClassVar[tuple[str, ...] | None] = None
    _arr: NDArray[NpStructT]

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Construct a single-sample payload. Structured dtypes use keyword arguments; scalar dtypes use a single positional argument."""
        if self._dtype.names is not None:
            # Structured dtype — keyword-only construction
            if args:
                raise TypeError(
                    f"{type(self).__name__}() requires keyword arguments, got positional args"
                )
            unknown = set(kwargs) - set(self._dtype.names)
            if unknown:
                raise TypeError(f"{type(self).__name__}() got unexpected kwargs: {sorted(unknown)}")
            values = tuple(kwargs[n] for n in self._dtype.names)
            self._arr = np.array([values], dtype=self._dtype)
        else:
            # Scalar dtype — single positional value
            if len(args) != 1 or kwargs:
                raise TypeError(f"{type(self).__name__}() takes exactly one positional argument")
            self._arr = np.array([args[0]], dtype=self._dtype)

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Ensure _dtype is a proper np.dtype when defined on the subclass.
        if "_dtype" in cls.__dict__:
            raw = cls.__dict__["_dtype"]
            if not isinstance(raw, np.dtype):
                cls._dtype = np.dtype(raw)

    @classmethod
    def from_buffer(cls, buf: bytes | bytearray | memoryview) -> Self:
        """Construct from a raw byte buffer interpreted as an array of ``_dtype`` records."""
        arr = np.frombuffer(buf, dtype=cls._dtype)
        obj = cls.__new__(cls)
        obj._arr = arr
        return obj

    @property
    def value(self) -> NDArray[NpStructT]:
        """Returns the backing array of ``_dtype`` records."""
        return self._arr

    @property
    def raw_payload(self) -> NDArray[NpStructT]:
        """Raw structured numpy array (alias for ``value``; useful for explicit byte serialisation)."""
        return self._arr

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to a DataFrame. Structured dtypes produce one column per field; scalar dtypes produce a ``"value"`` column."""
        if self._dtype.names is not None:
            return pd.DataFrame({name: self._arr[name] for name in self._dtype.names})
        return pd.DataFrame({"value": self._arr})

    def __len__(self) -> int:
        return len(self._arr)

    def _repr_kwargs(self) -> str:
        """Return the ``key=value`` portion used by ``__repr__`` and ``__str__``."""
        fields: tuple[str, ...]
        if self._repr_fields is not None:
            fields = self._repr_fields
        elif self._dtype.names is not None:
            fields = self._dtype.names
        else:
            return f"value={self.value!r}"
        return ", ".join(f"{f}={getattr(self, f)!r}" for f in fields)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._repr_kwargs()})"

    def __str__(self) -> str:
        return repr(self)


# ------------------------------------------------------------------
# Named scalar payload classes — one per PayloadType.
# These are the concrete types returned by RegisterU8, RegisterU16, etc.
# ------------------------------------------------------------------


class PayloadU8(PayloadBase[np.uint8]):
    _dtype: ClassVar = np.dtype("u1")


class PayloadU16(PayloadBase[np.uint16]):
    _dtype: ClassVar = np.dtype("<u2")


class PayloadU32(PayloadBase[np.uint32]):
    _dtype: ClassVar = np.dtype("<u4")


class PayloadU64(PayloadBase[np.uint64]):
    _dtype: ClassVar = np.dtype("<u8")


class PayloadS8(PayloadBase[np.int8]):
    _dtype: ClassVar = np.dtype("i1")


class PayloadS16(PayloadBase[np.int16]):
    _dtype: ClassVar = np.dtype("<i2")


class PayloadS32(PayloadBase[np.int32]):
    _dtype: ClassVar = np.dtype("<i4")


class PayloadS64(PayloadBase[np.int64]):
    _dtype: ClassVar = np.dtype("<i8")


class PayloadFloat(PayloadBase[np.float32]):
    _dtype: ClassVar = np.dtype("<f4")


# ------------------------------------------------------------------
# Array payload classes — one per PayloadType.
# Each message payload is a fixed-length array of the element type.
# Length is not stored on the class; pass it explicitly to
# ``from_buffer_with_length()``.
# ------------------------------------------------------------------


@final
class PayloadU8Array(PayloadBase[NDArray[np.uint8]]):
    _dtype: ClassVar = np.dtype("u1")


@final
class PayloadU16Array(PayloadBase[NDArray[np.uint16]]):
    _dtype: ClassVar = np.dtype("<u2")


@final
class PayloadU32Array(PayloadBase[NDArray[np.uint32]]):
    _dtype: ClassVar = np.dtype("<u4")


@final
class PayloadU64Array(PayloadBase[NDArray[np.uint64]]):
    _dtype: ClassVar = np.dtype("<u8")


@final
class PayloadS8Array(PayloadBase[NDArray[np.int8]]):
    _dtype: ClassVar = np.dtype("i1")


@final
class PayloadS16Array(PayloadBase[NDArray[np.int16]]):
    _dtype: ClassVar = np.dtype("<i2")


@final
class PayloadS32Array(PayloadBase[NDArray[np.int32]]):
    _dtype: ClassVar = np.dtype("<i4")


@final
class PayloadS64Array(PayloadBase[NDArray[np.int64]]):
    _dtype: ClassVar = np.dtype("<i8")


@final
class PayloadFloatArray(PayloadBase[NDArray[np.float32]]):
    _dtype: ClassVar = np.dtype("<f4")
