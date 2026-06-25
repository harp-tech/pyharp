def compute(data: bytes | bytearray | memoryview) -> int:
    """Wrapping u8 sum of all bytes except the last (the checksum byte itself)."""
    return sum(memoryview(data)[:-1]) & 0xFF


def validate(data: bytes | bytearray | memoryview) -> bool:
    """Return True if the last byte equals the checksum of all preceding bytes."""
    mv = memoryview(data)
    if len(mv) < 2:
        return False
    return compute(mv) == mv[-1]
