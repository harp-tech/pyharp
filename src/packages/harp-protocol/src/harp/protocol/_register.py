from abc import ABC, ABCMeta
from typing import Any, ClassVar, Generic, TypeVar, cast, final, overload

import numpy as np
from numpy.typing import NDArray
from typing_extensions import Sentinel

from ._builder import build_message_frame
from ._constants import (
    _DEFAULT_PORT,
    _HEADER_LEN,
    _TICK_PERIOD_S,
    _TIMESTAMP_FLAG,
    _TIMESTAMPED_PAYLOAD_OFFSET,
    _TS_MICROS_OFFSET,
)
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

U = TypeVar("U")
_R = TypeVar("_R")
_AR = TypeVar("_AR", bound="RegisterBase[Any]")


class _RegisterMeta(ABCMeta):
    """Calling a register class with an address creates a one-off subclass: ``RegisterU32(0x08)``."""

    def __call__(cls: "type[_R]", address: int) -> "type[_R]":
        return cast(
            "type[_R]",
            type(f"{cls.__name__}_{address:#04x}", (cls,), {"address": address}),
        )


class RegisterBase(ABC, Generic[U]):
    """Abstract base for all typed Harp registers.

    The generic parameter ``U`` is the static return type of :meth:`parse`:

    * scalar registers → a numpy scalar (e.g. ``np.uint16``);
    * array registers  → ``NDArray[…]`` of fixed length;
    * structured registers → the payload class itself.

    Subclasses must define ``address``, ``payload_type``, and
    ``payload_class`` as ``ClassVar``s.
    """

    address: ClassVar[int]
    payload_type: ClassVar[PayloadType]
    payload_class: ClassVar[type[PayloadBase[Any]]]
    length: ClassVar[int | None] = None

    @classmethod
    def parse(cls, value: HarpMessage | bytes | bytearray | memoryview) -> U:
        """Parse a single message into the user-facing payload value.

        Struct payloads return a typed wrapper (descriptor access like
        ``payload.Channel0`` works). Anonymous payloads (scalar / array
        registers) return the raw numpy scalar or ndarray directly.
        """
        buf = value.payload if isinstance(value, HarpMessage) else value
        record = np.frombuffer(buf, dtype=cls.payload_class.dtype, count=1)[0]
        return cast(U, cls.payload_class.unwrap(record))

    @classmethod
    def parse_bulk(
        cls,
        source: bytes | bytearray | memoryview,
        *,
        parse_timestamp: bool = True,
    ) -> "tuple[np.ndarray, np.ndarray | None, np.ndarray | None, Batch[Any]]":
        """Parse a bulk buffer containing one or more frames of this register type. Returns (data, timestamps, msgtype_view, payload)."""
        # Returns (data, timestamps, msgtype_view, payload). ``data`` is
        payload_cls = cls.payload_class
        data = np.frombuffer(source, dtype=np.uint8)

        if len(data) == 0:
            # No frames, but still need to return a Batch with the right dtype.
            payload = payload_cls.from_array(np.empty(0, dtype=payload_cls.dtype))
            return data, None, None, cast("Batch[Any]", payload)

        stride = (
            int(data[1]) + 2
        )  # TODO this assumes all frames have the same length but we may want to revisit in the future.
        nrows = len(data) // stride
        is_timestamped = bool(int(data[4]) & _TIMESTAMP_FLAG)
        payload_offset = _TIMESTAMPED_PAYLOAD_OFFSET if is_timestamped else _HEADER_LEN

        if is_timestamped and parse_timestamp:
            ts_s = np.ndarray(nrows, dtype="<u4", buffer=data, offset=_HEADER_LEN, strides=stride)
            ts_us = np.ndarray(
                nrows, dtype="<u2", buffer=data, offset=_TS_MICROS_OFFSET, strides=stride
            )
            timestamps = ts_s.astype(np.float64) + ts_us.astype(np.float64) * _TICK_PERIOD_S
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
        return data, timestamps, msgtype_view, cast("Batch[Any]", payload)

    @overload
    @classmethod
    def format(
        cls,
        *,
        message_type: MessageType = MessageType.Read,
        timestamp: float | None = None,
        port: int = _DEFAULT_PORT,
    ) -> bytes: ...

    @overload
    @classmethod
    def format(
        cls,
        value: U,
        *,
        message_type: MessageType = MessageType.Write,
        timestamp: float | None = None,
        port: int = _DEFAULT_PORT,
    ) -> bytes: ...
    # We go with "U" for typing but it is worth noting that we accept "Any" below.
    # However for API ergonomics we want to keep the type hint for symmetry
    @final
    @classmethod
    def format(
        cls,
        value: Any = _MISSING,
        *,
        message_type: MessageType | None = None,
        timestamp: float | None = None,
        port: int = _DEFAULT_PORT,
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
            elif isinstance(value, np.ndarray):
                raw = value.tobytes()
            else:
                # A bare high-level value (the symmetric counterpart of what
                # parse() returns): let the payload class encode it, so any
                # converter (e.g. a str via StringConverter) is applied.
                raw = cls.payload_class(value).raw_payload.tobytes()
            return build_message_frame(
                mt, cls.address, cls.payload_type, raw, port=port, timestamp=timestamp
            )


class RegisterU8(RegisterBase[np.uint8], metaclass=_RegisterMeta):
    """A simple scalar register with a uint8 payload. ``parse()`` returns ``np.uint8``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = PayloadU8


class RegisterU16(RegisterBase[np.uint16], metaclass=_RegisterMeta):
    """A simple scalar register with a uint16 payload. ``parse()`` returns ``np.uint16``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = PayloadU16


class RegisterU32(RegisterBase[np.uint32], metaclass=_RegisterMeta):
    """A simple scalar register with a uint32 payload. ``parse()`` returns ``np.uint32``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = PayloadU32


class RegisterU64(RegisterBase[np.uint64], metaclass=_RegisterMeta):
    """A simple scalar register with a uint64 payload. ``parse()`` returns ``np.uint64``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U64
    payload_class = PayloadU64


class RegisterS8(RegisterBase[np.int8], metaclass=_RegisterMeta):
    """A simple scalar register with a int8 payload. ``parse()`` returns ``np.int8``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S8
    payload_class = PayloadS8


class RegisterS16(RegisterBase[np.int16], metaclass=_RegisterMeta):
    """A simple scalar register with a int16 payload. ``parse()`` returns ``np.int16``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class = PayloadS16


class RegisterS32(RegisterBase[np.int32], metaclass=_RegisterMeta):
    """A simple scalar register with a int32 payload. ``parse()`` returns ``np.int32``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S32
    payload_class = PayloadS32


class RegisterS64(RegisterBase[np.int64], metaclass=_RegisterMeta):
    """A simple scalar register with a int64 payload. ``parse()`` returns ``np.int64``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S64
    payload_class = PayloadS64


class RegisterFloat(RegisterBase[np.float32], metaclass=_RegisterMeta):
    """A simple scalar register with a float32 payload. ``parse()`` returns ``np.float32``."""

    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class = PayloadFloat


class _ArrayRegisterMeta(ABCMeta):
    """A base metaclass for array registers. Calling with address and length creates a concrete subclass: ``RegisterU16Array(0x28, length=3)``."""

    def __call__(cls: "type[_AR]", address: int, *, length: int) -> "type[_AR]":  # type: ignore[override, misc]
        base_payload = cls.payload_class  # type: ignore[attr-defined]
        # Anonymous payloads carry a plain (non-structured) dtype. The array
        # variant uses a sub-dtype (inner_dtype, (length,)) so a single buffer
        # element decodes directly to an ndarray of shape (length,).
        inner = base_payload.dtype
        sub_dtype = np.dtype((inner, (length,)))
        concrete_payload = type(
            f"{base_payload.__name__}_{length}",
            (base_payload,),
            {"dtype": sub_dtype},
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


class RegisterU8Array(RegisterBase[NDArray[np.uint8]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a uint8 array payload. It must be instantiated with a length: ``RegisterU8Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.uint8]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = PayloadU8Array


class RegisterU16Array(RegisterBase[NDArray[np.uint16]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a uint16 array payload. It must be instantiated with a length: ``RegisterU16Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.uint16]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = PayloadU16Array


class RegisterU32Array(RegisterBase[NDArray[np.uint32]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a uint32 array payload. It must be instantiated with a length: ``RegisterU32Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.uint32]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = PayloadU32Array


class RegisterU64Array(RegisterBase[NDArray[np.uint64]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a uint64 array payload. It must be instantiated with a length: ``RegisterU64Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.uint64]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.U64
    payload_class = PayloadU64Array


class RegisterS8Array(RegisterBase[NDArray[np.int8]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int8 array payload. It must be instantiated with a length: ``RegisterS8Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.int8]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S8
    payload_class = PayloadS8Array


class RegisterS16Array(RegisterBase[NDArray[np.int16]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int16 array payload. It must be instantiated with a length: ``RegisterS16Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.int16]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class = PayloadS16Array


class RegisterS32Array(RegisterBase[NDArray[np.int32]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int32 array payload. It must be instantiated with a length: ``RegisterS32Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.int32]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S32
    payload_class = PayloadS32Array


class RegisterS64Array(RegisterBase[NDArray[np.int64]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a int64 array payload. It must be instantiated with a length: ``RegisterS64Array(0x28, length=3)``. ``parse()`` returns ``NDArray[np.int64]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.S64
    payload_class = PayloadS64Array


class RegisterFloatArray(RegisterBase[NDArray[np.float32]], metaclass=_ArrayRegisterMeta):
    """A simple array register with a float32 array payload. It must be instantiated with a length: ``RegisterFloatArray(0x28, length=3)``. ``parse()`` returns ``NDArray[np.float32]``."""

    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class = PayloadFloatArray
