"""Write Harp register data to a binary buffer or file, the inverse of the readers.

Thin wrappers over :meth:`RegisterBase.format_bulk` giving a pandas-package home
and a file sink. Useful for round-tripping data and generating typed test corpora.
"""

from os import PathLike
from typing import Any

import numpy as np
from harp.protocol import MessageType, PayloadBase, RegisterBase
from numpy.typing import ArrayLike, NDArray


def to_buffer(
    register: type[RegisterBase[Any]],
    values: PayloadBase | ArrayLike,
    *,
    timestamps: ArrayLike | None = None,
    message_type: MessageType | ArrayLike = MessageType.Event,
    port: int = 255,
) -> NDArray[np.uint8]:
    """Encode ``values`` as a flat buffer of ``register`` frames.

    ``values`` is a payload (scalar or batch) or an ndarray of the
    ``payload_class.payload_dtype``; ``timestamps`` (length-N seconds) makes every frame
    timestamped; ``message_type`` is one :class:`MessageType` or a length-N array
    (e.g. the msgtype view from ``parse_bulk``).
    """
    return register.format_bulk(values, timestamps=timestamps, message_type=message_type, port=port)


def to_file(
    register: type[RegisterBase[Any]],
    values: PayloadBase | ArrayLike,
    file: str | PathLike,
    *,
    timestamps: ArrayLike | None = None,
    message_type: MessageType | ArrayLike = MessageType.Event,
    port: int = 255,
) -> None:
    """Write ``values`` as ``register`` frames to ``file`` (see :func:`to_buffer`)."""
    to_buffer(register, values, timestamps=timestamps, message_type=message_type, port=port).tofile(
        file
    )
