import queue
import threading
from typing import Any, ClassVar, Self, TypeVar

import serial
from harp.protocol import HarpFramer, HarpMessage, MessageType
from harp.protocol._message import ParsedHarpMessage
from harp.protocol._payload import PayloadBase
from harp.protocol._register import RegisterBase

P = TypeVar("P", bound=PayloadBase[Any])


class SerialDevice:
    DEFAULT_BAUDRATE: ClassVar[int] = 1_000_000
    REPLY_TIMEOUT: float = 5.0  # seconds

    def __init__(
        self, port: str, baudrate: int = DEFAULT_BAUDRATE, raise_on_error: bool = True
    ) -> None:
        self._serial = serial.Serial(port, baudrate, timeout=0.1)
        self._serial.dtr = True

        self._framer = HarpFramer()
        self._pending: dict[int, queue.SimpleQueue] = {}
        self._pending_lock = threading.Lock()
        self._running = True
        self.raise_on_error = raise_on_error

        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name="harp-serial-device"
        )
        self._thread.start()

    def read_register(self, register: type[RegisterBase[P]]) -> ParsedHarpMessage[P]:
        frame = register.format()
        msg = self._request(register.address, frame)
        return ParsedHarpMessage.from_message(msg, register.parse(msg))

    def write_register(self, register: type[RegisterBase[P]], value: Any) -> ParsedHarpMessage[P]:
        frame = register.format(value)
        msg = self._request(register.address, frame)
        return ParsedHarpMessage.from_message(msg, register.parse(msg))

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=2.0)
        try:
            self._serial.dtr = False
        except Exception:
            pass
        self._serial.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _on_event(self, msg: HarpMessage) -> None:
        """Called from the reader thread when an Event message arrives.

        Override in subclasses to handle device-specific events.
        The default implementation discards the message.
        """

    def _read_loop(self) -> None:
        while self._running:
            try:
                waiting = self._serial.in_waiting
                chunk = self._serial.read(waiting if waiting > 0 else 1)
            except serial.SerialException:
                if self._running:
                    raise
                break

            if not chunk:
                continue

            self._framer.feed(chunk)
            for msg in self._framer.frames():
                self._dispatch(msg)

    def _dispatch(self, msg: HarpMessage) -> None:
        if msg.message_type in (MessageType.Read, MessageType.Write):
            with self._pending_lock:
                q = self._pending.get(msg.address)
            if q is not None:
                q.put(msg)
        elif msg.message_type == MessageType.Event:
            self._on_event(msg)
        else:
            # Unknown message type
            with self._pending_lock:
                q = self._pending.get(msg.address)
            if q is not None:
                q.put(msg)

    def _request(self, address: int, frame: bytes) -> HarpMessage:
        q: queue.SimpleQueue = queue.SimpleQueue()
        with self._pending_lock:
            self._pending[address] = q
        try:
            self._serial.write(frame)
            try:
                msg = q.get(timeout=self.REPLY_TIMEOUT)
                if msg.has_error and self.raise_on_error:
                    raise RuntimeError(
                        f"Device returned error for register address {address} "
                        f"(0x{address:02x}). Payload: {msg.payload.hex()}"
                    )
                return msg
            except queue.Empty as exc:
                raise TimeoutError(
                    f"No reply from device for register address {address} "
                    f"within {self.REPLY_TIMEOUT}s"
                ) from exc
        finally:
            with self._pending_lock:
                self._pending.pop(address, None)
