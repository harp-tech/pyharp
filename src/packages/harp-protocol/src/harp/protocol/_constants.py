"""Package-wide Harp protocol constants."""

_TICK_PERIOD_S: float = 32e-6
"""Harp timestamp clock tick period in seconds, 32 microseconds per tick."""

_TIMESTAMP_FLAG: int = 0x10
"""Payload-type byte bit that signals a timestamp is present in the frame."""

_DEFAULT_PORT: int = 0xFF
"""Default Harp port value, meaning broadcast."""

_HEADER_LEN: int = 5
"""Fixed header size in bytes: msg_type + length + address + port + payload_type."""

_MIN_FRAME_LEN: int = 6
"""Smallest frame on the wire in bytes, the fixed header plus the checksum."""

_TIMESTAMP_LEN: int = 6
"""Timestamp field size in bytes: 4-byte seconds as u32 plus 2-byte microseconds as u16."""

_TS_MICROS_OFFSET: int = 9
"""Byte offset of the timestamp microseconds field, which is ``_HEADER_LEN + 4``."""

_TIMESTAMPED_PAYLOAD_OFFSET: int = 11
"""Byte offset of the payload when a timestamp is present, ``_HEADER_LEN + _TIMESTAMP_LEN``."""
