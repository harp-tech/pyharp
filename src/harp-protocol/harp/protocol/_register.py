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
import pandas as pd
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
    def _parse_buffer(
        cls,
        source: bytes | bytearray | memoryview | Path | str,
        *,
        parse_timestamp: bool = True,
    ) -> "tuple[np.ndarray, np.ndarray | None, np.ndarray | None, P]":
        """Internal: parse a buffer once, returning (data, timestamps, msgtype_view, payload).

        ``timestamps`` is None when the register is not timestamped **or**
        when ``parse_timestamp`` is False (skips the float64 conversion).
        ``msgtype_view`` is a strided uint8 view (zero-copy, always computed).
        Returns ``data`` so its lifetime anchors the strided views.
        """
        if isinstance(source, (str, Path)):
            data = np.fromfile(source, dtype=np.uint8)
        else:
            data = np.frombuffer(source, dtype=np.uint8)

        if len(data) == 0:
            obj = cls.payload_class.__new__(cls.payload_class)
            obj._arr = np.empty(0, dtype=cls.payload_class._dtype.base)
            return data, None, None, cast(P, obj)

        stride = int(data[1]) + 2
        nrows = len(data) // stride
        is_timestamped = bool(int(data[4]) & 0x10)
        payload_offset = 11 if is_timestamped else 5

        if is_timestamped and parse_timestamp:
            ts_s = np.ndarray(nrows, dtype="<u4", buffer=data, offset=5, strides=stride)
            ts_us = np.ndarray(nrows, dtype="<u2", buffer=data, offset=9, strides=stride)
            timestamps = ts_s.astype(np.float64) + ts_us.astype(np.float64) * 32e-6
        else:
            timestamps = None

        msgtype_view = np.ndarray(nrows, dtype=np.uint8, buffer=data, offset=0, strides=stride)

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
            payload_arr = payload_arr[:, 0]

        obj = cls.payload_class.__new__(cls.payload_class)
        obj._arr = payload_arr
        return data, timestamps, msgtype_view, cast(P, obj)

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
            For non-timestamped registers, a synthetic ``arange(N)`` is
            returned.
        payload : P
            Payload object whose ``_arr`` is a zero-copy strided view into
            the raw buffer (shape ``(N,)`` for scalar/bitfield registers,
            ``(N, length)`` for array registers).
        """
        _data, timestamps, _msg, payload = cls._parse_buffer(source, parse_timestamp=True)
        if timestamps is None:
            timestamps = np.arange(len(payload), dtype=np.float64)
        return timestamps, payload

    @classmethod
    def read_dataframe(
        cls,
        source: bytes | bytearray | memoryview | Path | str,
        *,
        timestamp: bool = True,
        message_type: bool = False,
        decode_enums: bool = True,
    ) -> "pd.DataFrame":
        """One-call read: parse all frames into a DataFrame.

        Parameters
        ----------
        timestamp:
            Insert a ``timestamp`` column (float seconds). For non-timestamped
            registers this falls back to a synthetic frame index.
        message_type:
            Insert a ``message_type`` column as a ``pd.Categorical`` with
            categories ``["Read", "Write", "Event"]`` (high bits masked off).
        decode_enums:
            If True (default), ``_GroupMask`` payload fields are decoded to
            ``pd.Categorical`` columns using the enum member names.
            Set False for raw integer columns and minimum overhead.
        """

        _data, timestamps, msg_view, payload = cls._parse_buffer(source, parse_timestamp=timestamp)
        df = payload.to_dataframe(decode_enums=decode_enums)
        if message_type and msg_view is not None:
            _msg_names = np.array(["", "Read", "Write", "Event"])
            df.insert(
                0,
                "message_type",
                pd.Categorical(_msg_names[msg_view & 0x03], categories=_msg_names[1:]),
            )
        if timestamp:
            if timestamps is None:
                timestamps = np.arange(len(payload), dtype=np.float64)
            df.insert(0, "timestamp", timestamps)
        return df

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
