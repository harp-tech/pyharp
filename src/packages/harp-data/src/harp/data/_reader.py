"""Load Harp register data into pandas DataFrames."""

from pathlib import Path
from typing import Any, BinaryIO, Union

import numpy as np
import pandas as pd
from harp.protocol import Column, RegisterBase

Source = Union[str, Path, bytes, bytearray, memoryview, BinaryIO]

_MSG_NAMES = np.array(["_NONE", "Read", "Write", "Event"])


def _read_bytes(source: Source) -> bytes:
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source)
    if hasattr(source, "read"):  # open binary file / stream
        return source.read()
    return Path(source).read_bytes()

_DEFAULT_COLUMN_NAME = "value"


def columns_to_dataframe(columns: list[Column]) -> pd.DataFrame:
    """Assemble :class:`~harp.protocol.Column` objects into a DataFrame.

    Enum-backed columns (``categories`` set) become ``pd.Categorical`` built
    from codes — no string materialization; everything else is used as-is.
    """
    return pd.DataFrame(
        {
            (c.name if c.name is not None else _DEFAULT_COLUMN_NAME): (
                pd.Categorical.from_codes(c.data, categories=c.categories)
                if c.categories is not None
                else c.data
            )
            for c in columns
        }
    )


def to_dataframe(
    payload: Any, *, decode_enums: bool = True, demux_bit_masks: bool = False
) -> pd.DataFrame:
    """Turn a (batched) payload into a DataFrame, one row per frame.

    ``decode_enums`` relabels enum columns as ``pd.Categorical``; ``demux_bit_masks``
    expands each flag (``BitMask``) column into one boolean column per flag member.
    """
    # TODO: we may need to account for cases where columns have the same name.
    # this can happen when demuxing bitmasks, for example, where each bitmask column 
    # is expanded into multiple boolean columns with the same name. 
    return columns_to_dataframe(
        payload.to_columns(decode_enums=decode_enums, demux_bit_masks=demux_bit_masks)
    )


def read_dataframe(
    register: type[RegisterBase[Any]],
    source: Source,
    *,
    timestamp: bool = True,
    message_type: bool = False,
    decode_enums: bool = True,
    demux_bit_masks: bool = False,
) -> pd.DataFrame:
    """Parse all frames of ``register`` from ``source`` into a DataFrame.

    ``source`` may be a file path, raw bytes, or an open binary file object.
    ``timestamp`` and ``message_type`` insert leading columns; ``decode_enums``
    controls whether enum fields become ``pd.Categorical`` (True) or raw codes;
    ``demux_bit_masks`` expands each flag (``BitMask``) field into one boolean
    column per flag member (True) or keeps it as a single raw-integer column.
    """
    raw = _read_bytes(source)
    _data, timestamps, msg_view, payload = register.parse_bulk(raw, parse_timestamp=timestamp)
    df = to_dataframe(payload, decode_enums=decode_enums, demux_bit_masks=demux_bit_masks)

    if message_type and msg_view is not None:
        df.insert(
            0,
            "message_type",
            pd.Categorical(_MSG_NAMES[msg_view & 0x03], categories=_MSG_NAMES[1:]),
        )
    if timestamp:
        if timestamps is None:
            raise ValueError(
                "Buffer contains no timestamp data; pass timestamp=False to suppress "
                "the timestamp column."
            )
        df.insert(0, "timestamp", timestamps)
    return df
