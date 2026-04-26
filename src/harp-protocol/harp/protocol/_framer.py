from collections.abc import Iterator
from pathlib import Path

from ._message import HarpMessage, HarpParseError, parse
from ._message_type import from_byte as _validate_message_type


class HarpFramer:
    """Stateful Harp message stream parser.

    Feed raw bytes incrementally with feed(), then drain complete frames with
    next_frame() or by iterating. Suitable for both file parsing and streaming
    sources (e.g. serial ports) where data arrives in chunks.

    Recovery: on checksum or PayloadType failure, the framer skips exactly the
    bad MessageType byte and retries from the next byte — matching the C#
    StreamTransport resynchronisation strategy.
    """

    def __init__(self) -> None:
        self._buf: bytearray = bytearray()
        self._pos: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed(self, data: bytes | bytearray) -> None:
        """Append new bytes to the internal buffer."""
        self._buf.extend(data)
        # Compact once we've consumed a decent chunk to avoid unbounded growth.
        if self._pos > 4096:
            del self._buf[: self._pos]
            self._pos = 0

    def next_frame(self) -> HarpMessage | None:
        """Return the next complete, valid HarpMessage, or None if not enough data."""
        buf = self._buf
        pos = self._pos

        while pos < len(buf):
            # ── State 1: Seek ──────────────────────────────────────────────
            # Find a byte that looks like a valid MessageType.
            try:
                _validate_message_type(buf[pos])
            except ValueError:
                pos += 1
                continue

            msg_type_pos = pos

            # ── State 2: ReadLength ────────────────────────────────────────
            if pos + 1 >= len(buf):
                break  # need more data

            length = buf[pos + 1]
            if length == 0:
                # Length=0 is invalid (no remaining bytes, not even checksum).
                pos += 1
                continue

            # ── State 3: ReadBody ──────────────────────────────────────────
            frame_end = pos + 2 + length
            if frame_end > len(buf):
                break  # frame not yet complete

            frame = bytes(buf[pos:frame_end])
            try:
                msg = parse(frame)
                pos = frame_end
                self._pos = pos
                return msg
            except HarpParseError:
                # Recovery: skip the bad MessageType byte, retry from pos+1.
                pos = msg_type_pos + 1
                continue

        self._pos = pos
        return None

    def frames(self) -> Iterator[HarpMessage]:
        """Yield all complete frames currently available in the buffer."""
        while (msg := self.next_frame()) is not None:
            yield msg

    def __iter__(self) -> Iterator[HarpMessage]:
        return self.frames()

    # ------------------------------------------------------------------
    # Convenience class methods
    # ------------------------------------------------------------------

    @classmethod
    def parse_bytes(cls, data: bytes | bytearray) -> list[HarpMessage]:
        """Parse all Harp messages from a byte buffer."""
        framer = cls()
        framer.feed(data)
        return list(framer.frames())

    @classmethod
    def parse_file(cls, path: str | Path) -> list[HarpMessage]:
        """Parse all Harp messages from a binary file."""
        with open(path, "rb") as f:
            data = f.read()
        return cls.parse_bytes(data)
