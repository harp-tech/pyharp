"""Package-wide Harp protocol constants."""

# Harp timestamp clock tick period in seconds (32 µs/tick).
_TICK_PERIOD_S: float = 32e-6

# Payload-type byte bit that signals a timestamp is present in the frame.
_TIMESTAMP_FLAG: int = 0x10

# Default Harp port value (broadcast).
_DEFAULT_PORT: int = 0xFF

# Fixed header size in bytes: msg_type + length + address + port + payload_type.
_HEADER_LEN: int = 5

# Timestamp field size in bytes: 4-byte seconds (u32) + 2-byte microseconds (u16).
_TIMESTAMP_LEN: int = 6

# Byte offset of the timestamp microseconds field (_HEADER_LEN + 4).
_TS_MICROS_OFFSET: int = 9

# Byte offset of the payload when a timestamp is present (_HEADER_LEN + _TIMESTAMP_LEN).
_TIMESTAMPED_PAYLOAD_OFFSET: int = 11
