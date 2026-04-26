def compute(data: bytes | bytearray | memoryview) -> int:
    """Wrapping u8 sum of all bytes except the last (the checksum byte itself)."""
    total = 0
    mv = memoryview(bytes(data)) if not isinstance(data, (bytes, bytearray, memoryview)) else data
    for b in mv[:-1]:
        total = (total + b) & 0xFF
    return total


def validate(data: bytes | bytearray | memoryview) -> bool:
    """Return True if the last byte equals the checksum of all preceding bytes."""
    mv = memoryview(bytes(data)) if not isinstance(data, (bytes, bytearray, memoryview)) else data
    if len(mv) < 2:
        return False
    return compute(mv) == mv[-1]
