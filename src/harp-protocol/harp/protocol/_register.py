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
    Batch,
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
    payload_class: ClassVar[type[PayloadBase[Any]]]
    length: ClassVar[int | None] = None

    @classmethod
    def parse(cls, value: HarpMessage | bytes | bytearray | memoryview) -> P:
        """Parse a single message into a 0-D payload. It will only try to parse the first structured record if the payload is an array."""
        buf = value.payload if isinstance(value, HarpMessage) else value
        record = np.frombuffer(buf, dtype=cls.payload_class.dtype, count=1)[0]
        return cast(P, cls.payload_class.from_array(record))

    @classmethod
    def parse_bulk(
        cls,
        source: bytes | bytearray | memoryview,
        *,
        parse_timestamp: bool = True,
    ) -> "tuple[np.ndarray, np.ndarray | None, np.ndarray | None, Batch[P]]":
        """Parse a bulk buffer containing one or more frames of this register type. Returns (data, timestamps, msgtype_view, payload)."""
        # Returns (data, timestamps, msgtype_view, payload). ``data`` is
        payload_cls = cls.payload_class
        data = np.frombuffer(source, dtype=np.uint8)

        if len(data) == 0:
            # No frames, but still need to return a Batch with the right dtype.
            payload = payload_cls.from_array(np.empty(0, dtype=payload_cls.dtype))
            return data, None, None, cast("Batch[P]", payload)

        stride = (
            int(data[1]) + 2
        )  # TODO this assumes all frames have the same length but we may want to revisit in the future.
        nrows = len(data) // stride
        is_timestamped = bool(int(data[4]) & 0x10)
        payload_offset = 11 if is_timestamped else 5

        if is_timestamped and parse_timestamp:
            ts_s = np.ndarray(nrows, dtype="<u4", buffer=data, offset=5, strides=stride)
            ts_us = np.ndarray(nrows, dtype="<u2", buffer=data, offset=9, strides=stride)
            timestamps = ts_s.astype(np.float64) + ts_us.astype(np.float64) * 32e-6
        # TODO we may want to check if the timestamp is not present and users ask to be parsed. In that case we can either raise an error or return a nan-filled array
        else:
            timestamps = None

        msgtype_view = np.ndarray(nrows, dtype=np.uint8, buffer=data, offset=0, strides=stride)

        payload_arr = np.ndarray(
            nrows,
            dtype=payload_cls.dtype,
            buffer=data,
            offset=payload_offset,
            strides=stride,
        )

        payload = payload_cls.from_array(payload_arr)
        return data, timestamps, msgtype_view, cast("Batch[P]", payload)

    @classmethod
    def read_dataframe(
        cls,
        source: bytes | bytearray | memoryview,
        *,
        timestamp: bool = True,
        message_type: bool = False,
        decode_enums: bool = True,
    ) -> "pd.DataFrame":
        """Parse all frames into a DataFrame.

        ``timestamp`` and ``message_type`` insert leading columns.
        ``decode_enums`` controls whether ``_GroupMask`` slots become
        ``pd.Categorical`` (True) or raw integers (False).
        """
        _data, timestamps, msg_view, payload = cls.parse_bulk(source, parse_timestamp=timestamp)
        df = payload.to_dataframe(decode_enums=decode_enums)
        if message_type and msg_view is not None:
            _msg_names = np.array(["_NONE", "Read", "Write", "Event"])
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
                raw = value.raw_payload.tobytes()
            elif isinstance(value, np.ndarray) and value.dtype != cls.payload_type.numpy_dtype:
                raw = value.tobytes()
            else:
                raw = np.asarray(value, dtype=cls.payload_type.numpy_dtype).tobytes()
            return build_message_frame(
                mt, cls.address, cls.payload_type, raw, port=port, timestamp=timestamp
            )


class RegisterU8(RegisterBase[PayloadU8], metaclass=_RegisterMeta):
    """A simple scalar register with a uint8 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = PayloadU8


class RegisterU16(RegisterBase[PayloadU16], metaclass=_RegisterMeta):
    """A simple scalar register with a uint16 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = PayloadU16


class RegisterU32(RegisterBase[PayloadU32], metaclass=_RegisterMeta):
    """A simple scalar register with a uint32 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = PayloadU32


class RegisterU64(RegisterBase[PayloadU64], metaclass=_RegisterMeta):
    """A simple scalar register with a uint64 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.U64
    payload_class = PayloadU64


class RegisterS8(RegisterBase[PayloadS8], metaclass=_RegisterMeta):
    """A simple scalar register with a int8 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.S8
    payload_class = PayloadS8


class RegisterS16(RegisterBase[PayloadS16], metaclass=_RegisterMeta):
    """A simple scalar register with a int16 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class = PayloadS16


class RegisterS32(RegisterBase[PayloadS32], metaclass=_RegisterMeta):
    """A simple scalar register with a int32 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.S32
    payload_class = PayloadS32


class RegisterS64(RegisterBase[PayloadS64], metaclass=_RegisterMeta):
    """A simple scalar register with a int64 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.S64
    payload_class = PayloadS64


class RegisterFloat(RegisterBase[PayloadFloat], metaclass=_RegisterMeta):
    """A simple scalar register with a float32 payload."""

    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class = PayloadFloat


class _ArrayRegisterMeta(ABCMeta):
    """A base metaclass for array registers. Calling with address and length creates a concrete subclass: ``RegisterU16Array(0x28, length=3)``."""

    def __call__(cls: "type[_AR]", address: int, *, length: int) -> "type[_AR]":  # type: ignore[override, misc]
        from ._payload import _Field, _IdentityConverter

        base_payload = cls.payload_class  # type: ignore[attr-defined]
        inner = base_payload.dtype.fields["value"][0]
        sub_dtype = np.dtype((inner, (length,)))
        concrete_payload = type(
            f"{base_payload.__name__}_{length}",
            (base_payload,),
            {"value": _Field(_IdentityConverter(sub_dtype), name="value")},  # we
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
    """A simple array register with a uint8 array payload. It must be instantiated with a length: ``RegisterU8Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = PayloadU8Array


class RegisterU16Array(RegisterBase[PayloadU16Array], metaclass=_ArrayRegisterMeta):
    """A simple array register with a uint16 array payload. It must be instantiated with a length: ``RegisterU16Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = PayloadU16Array


class RegisterU32Array(RegisterBase[PayloadU32Array], metaclass=_ArrayRegisterMeta):
    """A simple array register with a uint32 array payload. It must be instantiated with a length: ``RegisterU32Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = PayloadU32Array


class RegisterU64Array(RegisterBase[PayloadU64Array], metaclass=_ArrayRegisterMeta):
    """A simple array register with a uint64 array payload. It must be instantiated with a length: ``RegisterU64Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U64
    payload_class = PayloadU64Array


class RegisterS8Array(RegisterBase[PayloadS8Array], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int8 array payload. It must be instantiated with a length: ``RegisterS8Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S8
    payload_class = PayloadS8Array


class RegisterS16Array(RegisterBase[PayloadS16Array], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int16 array payload. It must be instantiated with a length: ``RegisterS16Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class = PayloadS16Array


class RegisterS32Array(RegisterBase[PayloadS32Array], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int32 array payload. It must be instantiated with a length: ``RegisterS32Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S32
    payload_class = PayloadS32Array


class RegisterS64Array(RegisterBase[PayloadS64Array], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int64 array payload. It must be instantiated with a length: ``RegisterS64Array(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S64
    payload_class = PayloadS64Array


class RegisterFloatArray(RegisterBase[PayloadFloatArray], metaclass=_ArrayRegisterMeta):
    """A simple array register with a float32 array payload. It must be instantiated with a length: ``RegisterFloatArray(0x28, length=3)``."""

    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class = PayloadFloatArray
