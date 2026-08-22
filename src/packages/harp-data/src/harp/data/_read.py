from datetime import datetime
from typing import Any

import pandas as pd
from harp.protocol import (
    PayloadType,
    RegisterBase,
    RegisterFloat,
    RegisterFloatArray,
    RegisterS8,
    RegisterS8Array,
    RegisterS16,
    RegisterS16Array,
    RegisterS32,
    RegisterS32Array,
    RegisterS64,
    RegisterS64Array,
    RegisterU8,
    RegisterU8Array,
    RegisterU16,
    RegisterU16Array,
    RegisterU32,
    RegisterU32Array,
    RegisterU64,
    RegisterU64Array,
    decode_payload_type,
)
from harp.protocol._constants import _HEADER_LEN, _TIMESTAMP_LEN

from ._reader import Source, _read_bytes, parse_to_dataframe

_SCALAR_REGISTER: dict[PayloadType, Any] = {
    PayloadType.U8: RegisterU8,
    PayloadType.S8: RegisterS8,
    PayloadType.U16: RegisterU16,
    PayloadType.S16: RegisterS16,
    PayloadType.U32: RegisterU32,
    PayloadType.S32: RegisterS32,
    PayloadType.U64: RegisterU64,
    PayloadType.S64: RegisterS64,
    PayloadType.Float: RegisterFloat,
}

_ARRAY_REGISTER: dict[PayloadType, Any] = {
    PayloadType.U8: RegisterU8Array,
    PayloadType.S8: RegisterS8Array,
    PayloadType.U16: RegisterU16Array,
    PayloadType.S16: RegisterS16Array,
    PayloadType.U32: RegisterU32Array,
    PayloadType.S32: RegisterS32Array,
    PayloadType.U64: RegisterU64Array,
    PayloadType.S64: RegisterS64Array,
    PayloadType.Float: RegisterFloatArray,
}


def _infer_native_register(raw: bytes) -> type[RegisterBase[Any]]:
    """Build a native register class from the header of the first frame.

    Reads the payload-type byte, the length byte and the timestamp flag to derive
    the element type and element count, then returns the matching scalar or array
    register from :mod:`harp.protocol`.
    """
    if len(raw) < _HEADER_LEN:
        raise ValueError(f"buffer too short to contain a Harp frame header ({len(raw)} bytes)")
    info = decode_payload_type(raw[4])
    stride = int(raw[1]) + 2
    payload_offset = _HEADER_LEN + (_TIMESTAMP_LEN if info.has_timestamp else 0)
    payload_bytes = stride - payload_offset - 1  # trailing checksum byte
    count = payload_bytes // info.element_size
    address = int(raw[2])
    if count == 1:
        return _SCALAR_REGISTER[info.payload_type]
    return _ARRAY_REGISTER[info.payload_type](address, length=count)


def read(
    source: Source,
    *,
    time_index: bool = True,
    epoch: datetime | None = None,
    keep_type: bool = False,
) -> pd.DataFrame:
    """Read the binary data of a single register, inferring its native layout.

    ``source`` may be a file path, raw bytes, or an open binary file. The element
    type, length and timestamp presence are read from the first frame; values
    decode to the matching native numpy type (no enum or bit-mask decoding).
    The remaining options match :func:`~harp.data.parse_to_dataframe`.
    """
    raw = _read_bytes(source)
    if len(raw) == 0:
        return pd.DataFrame()
    register = _infer_native_register(raw)
    return parse_to_dataframe(
        register, raw, time_index=time_index, epoch=epoch, keep_type=keep_type
    )
