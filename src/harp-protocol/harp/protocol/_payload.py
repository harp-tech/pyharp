from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Generic, Self, TypeVar, final

import numpy as np
import pandas as pd
from numpy.typing import NDArray

if TYPE_CHECKING:
    from ._payload_type import PayloadType

ScalarT = TypeVar("ScalarT", bound=np.generic | np.ndarray)


class PayloadBase(Generic[ScalarT]):
    """Base class for typed Harp register payloads.

    Subclasses define ``_dtype: ClassVar[np.dtype]`` for the register layout::

        class AnalogDataPayload(PayloadBase):
            _dtype: ClassVar = np.dtype([
                ("analog_input0", "<i2"),
                ("encoder", "<i2"),
            ])
    """

    _dtype: ClassVar[np.dtype]
    _arr: NDArray[np.void]

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
    def scalar(cls, payload_type: "PayloadType") -> type[PayloadBase]:
        """Return a dynamically-generated ``PayloadBase`` subclass for a scalar type."""
        ## TODO we should prob consider removing this and just require explicit payload classes for all registers, even scalars. It's only a few lines of boilerplate to define a new one, and it would simplify the codebase by eliminating this dynamic class generation logic.

        dtype = payload_type.numpy_dtype
        name = f"_Scalar{payload_type.name}Payload"
        return type(name, (PayloadBase,), {"_dtype": dtype})

    @classmethod
    def from_buffer(cls, buf: bytes | bytearray | memoryview) -> Self:
        """Construct from a raw byte buffer interpreted as an array of ``_dtype`` records."""
        arr = np.frombuffer(buf, dtype=cls._dtype)
        obj = cls.__new__(cls)
        obj._arr = arr
        return obj

    @property
    def value(self) -> ScalarT:
        """Returns a single scalar if the array has one element, otherwise the full array."""
        if len(self._arr) == 1:
            return self._arr[0]  # type: ignore[return-value]
        return self._arr  # type: ignore[return-value]  # ty: ignore[invalid-return-type]

    @property
    def payload(self) -> NDArray[np.void]:
        """Raw structured numpy array."""
        return self._arr

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to a DataFrame. Structured dtypes produce one column per field; scalar dtypes produce a ``"value"`` column."""
        if self._dtype.names is not None:
            return pd.DataFrame({name: self._arr[name] for name in self._dtype.names})
        return pd.DataFrame({"value": self._arr})

    def __len__(self) -> int:
        return len(self._arr)


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
