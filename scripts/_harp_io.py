"""Verbatim copy of harp-python/harp/io.py `read` function.

Source: https://github.com/harp-tech/harp-python/blob/main/harp/io.py
Vendored here for the benchmark so we don't depend on the harp-python package
being installed.  Only `read` is included; `to_file`/`to_buffer` are omitted.

_BufferLike / _FileLike are inlined from harp/typing.py to keep this file
self-contained.
"""

import mmap
import sys
from datetime import datetime
from enum import IntEnum
from os import PathLike
from typing import Any, BinaryIO, Optional, Union

import numpy as np
import numpy.typing as npt
import pandas as pd

# ---------------------------------------------------------------------------
# Types (inlined from harp/typing.py)
# ---------------------------------------------------------------------------

if sys.version_info >= (3, 12):
    from collections.abc import Buffer as _BufferLike
else:
    _BufferLike = Union[bytes, bytearray, memoryview, mmap.mmap, npt.NDArray[Any]]

_FileLike = Union[str, "PathLike[str]", BinaryIO]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REFERENCE_EPOCH = datetime(1904, 1, 1)

_SECONDS_PER_TICK = 32e-6
_PAYLOAD_TIMESTAMP_MASK = 0x10


class MessageType(IntEnum):
    NA = 0
    READ = 1
    WRITE = 2
    EVENT = 3


_messagetypes = [t.name for t in MessageType]

_dtypefrompayloadtype = {
    1: np.dtype(np.uint8),
    2: np.dtype(np.uint16),
    4: np.dtype(np.uint32),
    8: np.dtype(np.uint64),
    129: np.dtype(np.int8),
    130: np.dtype(np.int16),
    132: np.dtype(np.int32),
    136: np.dtype(np.int64),
    68: np.dtype(np.float32),
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read(
    file_or_buf: Union[_FileLike, _BufferLike],
    address: Optional[int] = None,
    dtype: Optional[np.dtype] = None,
    length: Optional[int] = None,
    columns: Optional[list] = None,
    epoch: Optional[datetime] = None,
    keep_type: bool = False,
) -> pd.DataFrame:
    """Read single-register Harp data from the specified file or buffer.

    Returns a pandas DataFrame with a ``Time`` index (seconds as float64, or
    datetime if ``epoch`` is given).  Column order matches the payload layout.
    """
    if isinstance(file_or_buf, (str, PathLike, BinaryIO)) or hasattr(file_or_buf, "readinto"):
        data = np.fromfile(file_or_buf, dtype=np.uint8)  # type: ignore[arg-type]
    else:
        data = np.frombuffer(file_or_buf, dtype=np.uint8)  # type: ignore[arg-type]

    if len(data) == 0:
        return pd.DataFrame(
            columns=columns,
            index=(
                pd.DatetimeIndex([], name="Time")
                if epoch
                else pd.Index([], dtype=np.float64, name="Time")
            ),
        )

    if address is not None and address != data[2]:
        raise ValueError(f"expected address {address} but got {data[2]}")

    stride = int(data[1]) + 2
    nrows = len(data) // stride
    payloadtype = int(data[4])
    payloadoffset = 5
    index = None

    if payloadtype & _PAYLOAD_TIMESTAMP_MASK:
        seconds = np.ndarray(
            nrows, dtype=np.uint32, buffer=data, offset=payloadoffset, strides=stride
        )
        payloadoffset += 4
        micros = np.ndarray(
            nrows, dtype=np.uint16, buffer=data, offset=payloadoffset, strides=stride
        )
        payloadoffset += 2
        time = micros * _SECONDS_PER_TICK + seconds
        payloadtype = payloadtype & ~_PAYLOAD_TIMESTAMP_MASK
        if epoch is not None:
            time = epoch + pd.to_timedelta(time, "s")  # type: ignore[assignment]
            index = pd.DatetimeIndex(time)
            index.name = "Time"
        else:
            index = pd.Series(time)
            index.name = "Time"

    payloadsize = stride - payloadoffset - 1
    payload_dtype = _dtypefrompayloadtype[payloadtype]
    if dtype is not None and dtype != payload_dtype:
        raise ValueError(f"expected payload type {dtype} but got {payload_dtype}")

    elementsize = payload_dtype.itemsize
    payloadshape = (nrows, payloadsize // elementsize)
    if length is not None and length != payloadshape[1]:
        raise ValueError(f"expected payload length {length} but got {payloadshape[1]}")

    payload = np.ndarray(
        payloadshape,
        dtype=payload_dtype,
        buffer=data,
        offset=payloadoffset,
        strides=(stride, elementsize),
    )

    result = pd.DataFrame(payload, index=index, columns=columns)
    if keep_type:
        msgtype = np.ndarray(nrows, dtype=np.uint8, buffer=data, offset=0, strides=stride)
        result[MessageType.__name__] = pd.Categorical.from_codes(msgtype, categories=_messagetypes)
    return result
