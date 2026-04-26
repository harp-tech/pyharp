from dataclasses import dataclass
from enum import Enum

import numpy as np


class PayloadType(Enum):
    """Harp scalar payload types. Each value is the corresponding numpy dtype."""

    U8 = np.dtype("u1")
    U16 = np.dtype("<u2")
    U32 = np.dtype("<u4")
    U64 = np.dtype("<u8")
    S8 = np.dtype("i1")
    S16 = np.dtype("<i2")
    S32 = np.dtype("<i4")
    S64 = np.dtype("<i8")
    Float = np.dtype("<f4")

    @property
    def numpy_dtype(self) -> np.dtype:
        return self.value


@dataclass(frozen=True)
class PayloadTypeInfo:
    has_timestamp: bool
    payload_type: PayloadType
    element_size: int  # bytes per element


_SIZE_TO_UNSIGNED = {
    1: PayloadType.U8,
    2: PayloadType.U16,
    4: PayloadType.U32,
    8: PayloadType.U64,
}
_SIZE_TO_SIGNED = {
    1: PayloadType.S8,
    2: PayloadType.S16,
    4: PayloadType.S32,
    8: PayloadType.S64,
}


def decode_payload_type(b: int) -> PayloadTypeInfo:
    """Decode a PayloadType byte. Raises ``ValueError`` for invalid bytes."""
    size = b & 0x0F
    if size not in (1, 2, 4, 8):
        raise ValueError(f"Invalid size nibble {size} in PayloadType byte: 0x{b:02x}")
    if b & 0x20:
        raise ValueError(f"Reserved bit 5 set in PayloadType byte: 0x{b:02x}")

    has_timestamp = bool(b & 0x10)
    is_float = bool(b & 0x40)
    is_signed = bool(b & 0x80)

    if is_float and is_signed:
        raise ValueError(f"IsFloat and IsSigned cannot both be set: 0x{b:02x}")
    if is_float and (b & 0xEF) != 0x44:
        raise ValueError(f"Float payload must have size=4 only: 0x{b:02x}")

    if is_float:
        payload_type = PayloadType.Float
    elif is_signed:
        payload_type = _SIZE_TO_SIGNED[size]
    else:
        payload_type = _SIZE_TO_UNSIGNED[size]

    return PayloadTypeInfo(
        has_timestamp=has_timestamp, payload_type=payload_type, element_size=size
    )


def encode_payload_type(payload_type: PayloadType, *, has_timestamp: bool = False) -> int:
    """Encode a PayloadType back to a protocol byte."""
    dtype = payload_type.numpy_dtype
    kind = dtype.kind  # 'u', 'i', 'f'
    size = dtype.itemsize

    b = size
    if kind == "i":
        b |= 0x80
    elif kind == "f":
        b |= 0x40
    if has_timestamp:
        b |= 0x10
    return int(b)
