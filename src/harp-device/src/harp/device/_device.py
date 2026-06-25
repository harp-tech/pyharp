"""Transport-agnostic Harp device base class."""

from typing import Any, ClassVar, Self, TypeVar

import queue
import threading
from abc import ABC, abstractmethod

from harp.protocol import HarpMessage, MessageType
from harp.protocol._message import ParsedHarpMessage
from harp.protocol._register import RegisterBase

from ._framer import HarpFramer
from ._registers import (
    AssemblyVersion,
    ClockConfig,
    CoreVersionH,
    CoreVersionL,
    DeviceName,
    FirmwareVersionH,
    FirmwareVersionL,
    Heartbeat,
    HwVersionH,
    HwVersionL,
    OperationControl,
    ResetDevice,
    SerialNumber,
    TimestampMicro,
    TimestampOffset,
    TimestampSecond,
    WhoAmI,
)

P = TypeVar("P")


class Device(ABC):
    """Transport-agnostic base for Harp devices.

    Owns the protocol logic (framing, request/reply, register access).
    Subclasses supply a transport via the abstract :meth:`_write`/:meth:`_read`
    and the optional :meth:`_open`/:meth:`_close` hooks; they store transport
    config then call ``super().__init__()``, which connects and starts reading.

    Common registers are exposed as class attributes (``dev.read(dev.WhoAmI)``).
    Set :attr:`__whoami__` to have ``open()`` validate the device identity
    (``0x0`` skips the check).
    """

    REPLY_TIMEOUT: ClassVar[float] = 5.0  # seconds

    #: Expected ``WhoAmI`` of the device this class models; ``0x0`` skips the check.
    __whoami__: ClassVar[int] = 0x0

    # -- exposed registers --------------------------------------------------
    WhoAmI = WhoAmI
    HwVersionH = HwVersionH
    HwVersionL = HwVersionL
    AssemblyVersion = AssemblyVersion
    CoreVersionH = CoreVersionH
    CoreVersionL = CoreVersionL
    FirmwareVersionH = FirmwareVersionH
    FirmwareVersionL = FirmwareVersionL
    TimestampSecond = TimestampSecond
    TimestampMicro = TimestampMicro
    OperationControl = OperationControl
    ResetDevice = ResetDevice
    DeviceName = DeviceName
    SerialNumber = SerialNumber
    TimestampOffset = TimestampOffset
    ClockConfig = ClockConfig
    Heartbeat = Heartbeat

    def __init__(self, *, raise_on_error: bool = True) -> None:
        self.raise_on_error = raise_on_error
        self._framer = HarpFramer()
        self._pending: dict[int, queue.SimpleQueue] = {}
        self._pending_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self.open()

    # ------------------------------------------------------------------
    # Transport primitives (implemented by subclasses)
    # ------------------------------------------------------------------

    def _open(self) -> None:
        """Open the underlying transport. Default: no-op."""

    @abstractmethod
    def _write(self, data: bytes) -> None:
        """Send raw bytes over the transport."""

    @abstractmethod
    def _read(self) -> bytes:
        """Return available bytes, or ``b''`` on timeout/idle.

        Block only briefly so the read loop can poll ``_running``, and return
        ``b''`` rather than raise once the transport is closing.
        """

    def _close(self) -> None:
        """Close the underlying transport. Default: no-op."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> Self:
        self._open()
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name=f"{type(self).__name__}-reader"
        )
        self._thread.start()
        try:
            self._validate_whoami()
        except Exception:
            self.close()
            raise
        return self

    def _validate_whoami(self) -> None:
        """Check the device's ``WhoAmI`` against :attr:`__whoami__` (``0x0`` skips)."""
        expected = self.__whoami__
        if expected == 0x0:
            return
        actual = int(self.read(WhoAmI).parsed)
        if actual != expected:
            raise RuntimeError(
                f"WhoAmI mismatch: {type(self).__name__} expected 0x{expected:04x} "
                f"but device reported 0x{actual:04x}."
            )

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Register access
    # ------------------------------------------------------------------

    def read(
        self,
        register: type[RegisterBase[P]],
        *,
        timestamp: float | None = None,
        port: int = 255,
    ) -> ParsedHarpMessage[P]:
        # Note: ty can't correctly infer the return type, and this is a known issue:
        # https://github.com/astral-sh/ty/issues/623
        frame = register.format(message_type=MessageType.Read, timestamp=timestamp, port=port)
        msg = self._request(register.address, frame)
        return ParsedHarpMessage.from_message(msg, register.parse(msg))

    def write(
        self,
        register: type[RegisterBase[P]],
        value: Any,
        *,
        timestamp: float | None = None,
        port: int = 255,
    ) -> ParsedHarpMessage[P]:
        frame = register.format(
            value, message_type=MessageType.Write, timestamp=timestamp, port=port
        )
        msg = self._request(register.address, frame)
        return ParsedHarpMessage.from_message(msg, register.parse(msg))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_event(self, msg: HarpMessage) -> None:
        """Handle an Event message from the reader thread. Default: discard."""

    def _read_loop(self) -> None:
        while self._running:
            chunk = self._read()
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
            self._write(frame)
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
