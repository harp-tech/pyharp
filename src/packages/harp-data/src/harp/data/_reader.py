"""Load Harp register data into pandas DataFrames."""

from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Union

import numpy as np
import pandas as pd
from harp.protocol import RegisterBase
from numpy.typing import NDArray

Source = Union[str, Path, bytes, bytearray, memoryview, BinaryIO]

_MSG_NAMES = np.array(["_NONE", "Read", "Write", "Event"])

REFERENCE_EPOCH = datetime(1904, 1, 1)
"""Harp reference epoch, time zero of the Harp clock in UTC."""

_TIME_INDEX_NAME = "Time"


def _time_index(seconds: NDArray[np.float64], epoch: datetime | None) -> pd.Index:
    """The Harp time axis: float seconds, or absolute datetime when ``epoch`` is set."""
    if epoch is None:
        return pd.Index(seconds, name=_TIME_INDEX_NAME)
    return pd.DatetimeIndex(
        pd.Timestamp(epoch) + pd.to_timedelta(seconds, unit="s"), name=_TIME_INDEX_NAME
    )


def _read_bytes(source: Source) -> bytes:
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    return source.read()  # open binary file / stream


_DEFAULT_COLUMN_NAME = "value"


def payload_to_dataframe(
    payload: Any, *, decode_enums: bool = True, demux_bit_masks: bool = False, copy: bool = False
) -> pd.DataFrame:
    """Turn a (batched) payload into a DataFrame, one row per frame.

    ``decode_enums`` relabels enum columns as ``pd.Categorical``; ``demux_bit_masks``
    expands each flag (``BitMask``) column into one boolean column per flag member.
    """
    # TODO: we may need to account for cases where columns have the same name.
    # this can happen when demuxing bitmasks, for example, where each bitmask column
    # is expanded into multiple boolean columns with the same name.
    cols = payload.payload_as_columns(decode_enums=decode_enums, demux_bit_masks=demux_bit_masks)
    return pd.DataFrame(
        {
            (c.name if c.name is not None else _DEFAULT_COLUMN_NAME): (
                pd.Categorical.from_codes(c.data, categories=c.categories)
                if c.categories is not None
                else c.data
            )
            for c in cols
        },
        copy=copy,
    )


def parse_to_dataframe(
    register: type[RegisterBase[Any]],
    source: Source,
    *,
    timestamp: bool = True,
    epoch: Union[datetime, None] = None,
    message_type: bool = False,
    decode_enums: bool = True,
    demux_bit_masks: bool = False,
) -> pd.DataFrame:
    """Parse all frames of ``register`` from ``source`` into a DataFrame.

    ``source`` may be a file path, raw bytes, or an open binary file object. When
    ``timestamp`` is set, the Harp time becomes the DataFrame index (named
    ``"Time"``): float seconds by default, or an absolute ``DatetimeIndex`` when
    ``epoch`` is given (e.g. :data:`REFERENCE_EPOCH`). ``message_type`` inserts a
    leading column; ``decode_enums`` controls whether enum fields become
    ``pd.Categorical`` (True) or raw codes; ``demux_bit_masks`` expands each flag
    (``BitMask``) field into one boolean column per flag member (True) or keeps it
    as a single raw-integer column.
    """
    raw = _read_bytes(source)
    _data, timestamps, msg_view, payload = register.parse_bulk(raw, parse_timestamp=timestamp)
    df = payload_to_dataframe(payload, decode_enums=decode_enums, demux_bit_masks=demux_bit_masks)

    if message_type and msg_view is not None:
        df.insert(
            0,
            "message_type",
            pd.Categorical(_MSG_NAMES[msg_view & 0x03], categories=_MSG_NAMES[1:]),
        )
    if timestamp:
        if timestamps is None:
            if len(df) > 0:
                raise ValueError(
                    "Buffer contains no timestamp data; pass timestamp=False to suppress "
                    "the time index."
                )
            seconds = np.empty(0, dtype=np.float64)  # empty buffer: empty Time index
        else:
            seconds = np.asarray(timestamps, dtype=np.float64)
        df.index = _time_index(seconds, epoch)
    return df
