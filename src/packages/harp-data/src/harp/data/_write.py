"""Write Harp register data to a binary buffer/file — the inverse of the readers.

Thin wrappers over :meth:`RegisterBase.format_bulk` giving a pandas-package home
and a file sink. Useful for round-tripping data and generating typed test corpora.
"""

from os import PathLike
from typing import Any, Union

import numpy as np
from harp.protocol import MessageType, RegisterBase
from numpy.typing import NDArray


def to_buffer(
    register: type[RegisterBase[Any]],
    values: Any,
    *,
    timestamps: Any = None,
    message_type: Any = MessageType.Event,
    port: int = 255,
) -> NDArray[np.uint8]:
    """Encode ``values`` as a flat buffer of ``register`` frames.

    ``values`` is a payload (scalar or batch) or an ndarray of the register's
    ``payload_class.dtype``; ``timestamps`` (length-N seconds) makes every frame
    timestamped; ``message_type`` is one :class:`MessageType` or a length-N array
    (e.g. the msgtype view from ``parse_bulk``).
    """
    return register.format_bulk(values, timestamps=timestamps, message_type=message_type, port=port)


def to_file(
    register: type[RegisterBase[Any]],
    values: Any,
    file: Union[str, PathLike],
    *,
    timestamps: Any = None,
    message_type: Any = MessageType.Event,
    port: int = 255,
) -> None:
    """Write ``values`` as ``register`` frames to ``file`` (see :func:`to_buffer`)."""
    to_buffer(register, values, timestamps=timestamps, message_type=message_type, port=port).tofile(
        file
    )
