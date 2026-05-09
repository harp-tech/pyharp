"""Register base classes for the Harp protocol.

Define a register by subclassing the appropriate typed class::

    class TimestampSecond(RegisterU32):
        address: ClassVar[int] = 8

    TimestampSecond.format()     # → Read request frame
    TimestampSecond.format(42)   # → Write request frame
    TimestampSecond.parse(msg)   # → PayloadU32 instance
"""

from abc import ABC, ABCMeta
from pathlib import Path
from typing import Any, ClassVar, Generic, TypeVar, cast, final, overload

import numpy as np
from typing_extensions import Sentinel

from ._builder import build_message_frame
from ._message import HarpMessage
from ._message_type import MessageType
from ._payload import (
    PayloadBase,
    PayloadFloat,
    PayloadFloatArray,
    PayloadS8,
    PayloadS8Array,
    PayloadS16,
    PayloadS16Array,
    PayloadS32,
    PayloadS32Array,
    PayloadS64,
    PayloadS64Array,
    PayloadU8,
    PayloadU8Array,
    PayloadU16,
    PayloadU16Array,
    PayloadU32,
    PayloadU32Array,
    PayloadU64,
    PayloadU64Array,
)
from ._payload_type import PayloadType

_MISSING = Sentinel("_MISSING")

P = TypeVar("P", bound=PayloadBase[Any])
_R = TypeVar("_R")
_AR = TypeVar("_AR", bound="RegisterBase[Any]")


class _RegisterMeta(ABCMeta):
    """Calling a register class with an address creates a one-off subclass: ``RegisterU32(0x08)``."""

    def __call__(cls: "type[_R]", address: int) -> "type[_R]":
        return cast(
            "type[_R]",
            type(f"{cls.__name__}_{address:#04x}", (cls,), {"address": address}),
        )


class RegisterBase(ABC, Generic[P]):
    """Abstract base for all typed Harp registers.

    Subclasses must define ``address`` and ``payload_type`` as ``ClassVar``s.
    Optionally define ``payload_class`` for structured payloads; otherwise a scalar one is generated.
    """

    address: ClassVar[int]
    payload_type: ClassVar[PayloadType]
    payload_class: ClassVar[type[Any]]  # Gotta keep Any so children can override without warning.
    length: ClassVar[int | None] = None

    @classmethod
    def parse(cls, value: HarpMessage | bytes | bytearray | memoryview) -> P:
        """Parse the payload from a ``HarpMessage`` or raw bytes."""
        buf = value.payload if isinstance(value, HarpMessage) else value
        return cast(P, cls.payload_class.from_buffer(buf))

    @classmethod
    def read_frames(
        cls,
        source: bytes | bytearray | memoryview | Path | str,
    ) -> "tuple[np.ndarray, P]":
        """Read all frames from a single-register Harp binary buffer or file.

        Parameters
        ----------
        source:
            Raw bytes, a bytes-like object, or a path to a ``.bin`` file
            containing packed Harp frames for a single register.

        Returns
        -------
        timestamps : np.ndarray
            1-D float64 array of timestamps in seconds, one per frame.
        payload : P
            Payload object whose ``_arr`` is a zero-copy strided view into
            the raw buffer (shape ``(N,)`` for scalar/bitfield registers,
            ``(N, length)`` for array registers).
        """
        if isinstance(source, (str, Path)):
            data = np.fromfile(source, dtype=np.uint8)
        else:
            data = np.frombuffer(source, dtype=np.uint8)

        if len(data) == 0:
            obj = cls.payload_class.__new__(cls.payload_class)
            obj._arr = np.empty(0, dtype=cls.payload_class._dtype.base)
            return np.empty(0, dtype=np.float64), cast(P, obj)

        stride = int(data[1]) + 2
        nrows = len(data) // stride
        is_timestamped = bool(int(data[4]) & 0x10)
        payload_offset = 11 if is_timestamped else 5

        if is_timestamped:
            ts_s = np.ndarray(nrows, dtype="<u4", buffer=data, offset=5, strides=stride)
            ts_us = np.ndarray(nrows, dtype="<u2", buffer=data, offset=9, strides=stride)
            timestamps = ts_s.astype(np.float64) + ts_us.astype(np.float64) * 32e-6
        else:
            timestamps = np.arange(nrows, dtype=np.float64)

        # Use .base to unwrap sub-array dtypes created by _ArrayRegisterMeta
        elem_dtype = cls.payload_class._dtype.base
        elem_size = elem_dtype.itemsize
        length = cls.length or 1
        payload_arr = np.ndarray(
            (nrows, length),
            dtype=elem_dtype,
            buffer=data,
            offset=payload_offset,
            strides=(stride, elem_size),
        )
        if length == 1:
            payload_arr = payload_arr[:, 0]  # shape (N,) not (N, 1)

        obj = cls.payload_class.__new__(cls.payload_class)
        obj._arr = payload_arr
        return timestamps, cast(P, obj)

    @overload
    @classmethod
    def format(
        cls,
        *,
        message_type: MessageType = MessageType.Read,
        timestamp: float | None = None,
        port: int = 0xFF,
    ) -> bytes: ...

    @overload
    @classmethod
    def format(
        cls,
        value: Any,
        *,
        message_type: MessageType = MessageType.Write,
        timestamp: float | None = None,
        port: int = 0xFF,
    ) -> bytes: ...

    @final
    @classmethod
    def format(
        cls,
        value: Any = _MISSING,
        *,
        message_type: MessageType | None = None,
        timestamp: float | None = None,
        port: int = 0xFF,
    ) -> bytes:
        """Build a Harp frame for this register. No value → Read; with value → Write."""
        if value is _MISSING:
            mt = MessageType.Read if message_type is None else message_type
            return build_message_frame(
                mt, cls.address, cls.payload_type, port=port, timestamp=timestamp
            )
        else:
            mt = MessageType.Write if message_type is None else message_type
            if isinstance(value, PayloadBase):
                # Payload instance — use its backing array bytes directly
                raw = value.raw_payload.tobytes()
            elif isinstance(value, np.ndarray) and value.dtype != cls.payload_type.numpy_dtype:
                # Structured numpy array passed by hand
                raw = value.tobytes()
            else:
                # Scalar or array castable to the register's primitive dtype
                raw = np.asarray(value, dtype=cls.payload_type.numpy_dtype).tobytes()
            return build_message_frame(
                mt, cls.address, cls.payload_type, raw, port=port, timestamp=timestamp
            )


class RegisterU8(RegisterBase[PayloadU8], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class: ClassVar[type[PayloadU8]] = PayloadU8


class RegisterU16(RegisterBase[PayloadU16], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class: ClassVar[type[PayloadU16]] = PayloadU16


class RegisterU32(RegisterBase[PayloadU32], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class: ClassVar[type[PayloadU32]] = PayloadU32


class RegisterU64(RegisterBase[PayloadU64], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U64
    payload_class: ClassVar[type[PayloadU64]] = PayloadU64


class RegisterS8(RegisterBase[PayloadS8], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S8
    payload_class: ClassVar[type[PayloadS8]] = PayloadS8


class RegisterS16(RegisterBase[PayloadS16], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class: ClassVar[type[PayloadS16]] = PayloadS16


class RegisterS32(RegisterBase[PayloadS32], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S32
    payload_class: ClassVar[type[PayloadS32]] = PayloadS32


class RegisterS64(RegisterBase[PayloadS64], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S64
    payload_class: ClassVar[type[PayloadS64]] = PayloadS64


class RegisterFloat(RegisterBase[PayloadFloat], metaclass=_RegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class: ClassVar[type[PayloadFloat]] = PayloadFloat


class _ArrayRegisterMeta(ABCMeta):
    """Calling with address and length creates a concrete subclass: ``RegisterU16Array(0x28, length=3)``."""

    def __call__(cls: "type[_AR]", address: int, *, length: int) -> "type[_AR]":  # type: ignore[override, misc]
        base_payload = cls.payload_class  # type: ignore[attr-defined]
        concrete_payload = type(
            f"{base_payload.__name__}_{length}",
            (base_payload,),
            {"_dtype": np.dtype((base_payload._dtype, length))},  # type: ignore[attr-defined]
        )
        return cast(
            "type[_AR]",
            type(
                f"{cls.__name__}_{address:#04x}",
                (cls,),
                {
                    "address": address,
                    "length": length,
                    "payload_class": concrete_payload,
                },
            ),
        )


class RegisterU8Array(RegisterBase[PayloadU8Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class: ClassVar[type[Any]] = PayloadU8Array


class RegisterU16Array(RegisterBase[PayloadU16Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class: ClassVar[type[Any]] = PayloadU16Array


class RegisterU32Array(RegisterBase[PayloadU32Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class: ClassVar[type[Any]] = PayloadU32Array


class RegisterU64Array(RegisterBase[PayloadU64Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.U64
    payload_class: ClassVar[type[Any]] = PayloadU64Array


class RegisterS8Array(RegisterBase[PayloadS8Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S8
    payload_class: ClassVar[type[Any]] = PayloadS8Array


class RegisterS16Array(RegisterBase[PayloadS16Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class: ClassVar[type[Any]] = PayloadS16Array


class RegisterS32Array(RegisterBase[PayloadS32Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S32
    payload_class: ClassVar[type[Any]] = PayloadS32Array


class RegisterS64Array(RegisterBase[PayloadS64Array], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.S64
    payload_class: ClassVar[type[Any]] = PayloadS64Array


class RegisterFloatArray(RegisterBase[PayloadFloatArray], metaclass=_ArrayRegisterMeta):
    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class: ClassVar[type[Any]] = PayloadFloatArray
