"""Transport-agnostic Harp device base class."""

from collections.abc import Callable, Iterable
from typing import Any, ClassVar, Generic, Self, TypeVar, overload

import logging
import queue
import threading

from harp.protocol import HarpMessage, MessageType
from harp.protocol._message import ParsedHarpMessage
from harp.protocol._register import RegisterBase

from harp.device.schema import DeviceModuleLike
from ._framer import HarpFramer
from ._transport import ITransport, TransportError
from harp.device.core import (
    WhoAmI,
)

M = TypeVar("M", bound="DeviceModuleLike | None")
P = TypeVar("P")

_logger = logging.getLogger(__name__)

#: A callback receiving a typed, parsed event for a specific register.
EventHandler = Callable[[ParsedHarpMessage[P]], None]

#: Message types a subscription reacts to, as a single type or an iterable.
MessageTypeFilter = MessageType | Iterable[MessageType]

#: Default filter for :meth:`Device.subscribe`: unsolicited events only.
_DEFAULT_MESSAGE_TYPES: frozenset[MessageType] = frozenset({MessageType.Event})


def _normalize_message_types(message_types: MessageTypeFilter) -> frozenset[MessageType]:
    if isinstance(message_types, MessageType):
        return frozenset({message_types})
    return frozenset(message_types)


class Subscription:
    """Handle returned by :meth:`Device.subscribe`. Cancel with
    :meth:`unsubscribe`, or use as a context manager to auto-cancel on exit."""

    def __init__(
        self,
        device: "Device",
        address: int | None,
        handler: Callable[[Any], None],
        message_types: frozenset[MessageType],
    ) -> None:
        self._device = device
        self._address = address  # None => catch-all
        self._handler = handler
        self._message_types = message_types
        self._active = True

    def unsubscribe(self) -> None:
        """Stop delivering events to this subscription. Idempotent."""
        if self._active:
            self._device._remove_subscription(self)
            self._active = False

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *args: object) -> None:
        self.unsubscribe()


class Device(Generic[M]):
    """Harp device protocol logic (framing, request/reply, register access)
    over an :class:`~harp.device.client.ITransport`.

    Must be opened before use, via ``with`` or :meth:`open`. :meth:`read`,
    :meth:`write` and :meth:`subscribe` take a register class directly.

    Pass a ``device_module`` (from :func:`~harp.device.schema.create_device_module` or a
    statically generated device package) to validate device identity on open and
    pre-populate the register map for event parsing::

        behavior = create_device_module(schema_text)
        with Device(transport, behavior) as dev:
            dev.read(behavior.OperationControl)

    Omitting ``device_module`` skips identity validation and starts with an empty
    register map; individual registers can still be used via :meth:`read`,
    :meth:`write`, and :meth:`subscribe`.
    """

    REPLY_TIMEOUT: ClassVar[float] = 5.0  # seconds

    @overload
    def __init__(
        self, transport: ITransport, device_module: M, *, raise_on_error: bool = ...
    ) -> None: ...

    @overload
    def __init__(
        self: "Device[None]",
        transport: ITransport,
        device_module: None = ...,
        *,
        raise_on_error: bool = ...,
    ) -> None: ...

    def __init__(
        self,
        transport: ITransport,
        device_module: M | None = None,
        *,
        raise_on_error: bool = True,
    ) -> None:
        self._transport = transport
        self._device_module = device_module
        self.raise_on_error = raise_on_error
        self._framer = HarpFramer()
        self._pending: dict[int, queue.SimpleQueue] = {}
        self._pending_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        # Event subscriptions, delivered off the reader thread (see _event_loop).
        self._subscriptions: dict[int, list[Subscription]] = {}
        self._registers: dict[int, type[RegisterBase[Any]]] = {}
        self._catch_all: list[Subscription] = []
        self._sub_lock = threading.Lock()
        self._event_queue: queue.SimpleQueue[HarpMessage | None] = queue.SimpleQueue()
        self._event_thread: threading.Thread | None = None

    @property
    def module(self) -> M:
        """The device module injected at construction, or ``None`` if not set."""
        return self._device_module  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> Self:
        """Open the transport, start the reader thread and validate identity."""
        self._transport.open()
        self._running = True
        self._event_thread = threading.Thread(
            target=self._event_loop, daemon=True, name=f"{type(self).__name__}-events"
        )
        self._event_thread.start()
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
        """Check the device's ``WhoAmI`` against the module (skipped if no module or ``WHO_AM_I == 0x0``)."""
        if self._device_module is None:
            return
        expected = self._device_module.WHO_AM_I
        if expected == 0x0:
            return
        actual = int(self.read(WhoAmI).parsed)
        if actual != expected:
            raise RuntimeError(
                f"WhoAmI mismatch: expected 0x{expected:04x} but device reported 0x{actual:04x}."
            )

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._event_thread is not None:
            self._event_queue.put(None)  # wake the loop so it can exit
            self._event_thread.join(timeout=2.0)
            self._event_thread = None
        self._transport.close()
        with self._sub_lock:
            self._subscriptions.clear()
            self._registers.clear()
            self._catch_all.clear()

    def __enter__(self) -> Self:
        if not self._running:
            self.open()
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
    # Events
    # ------------------------------------------------------------------

    def subscribe(
        self,
        register: type[RegisterBase[P]],
        handler: EventHandler[P],
        *,
        message_types: MessageTypeFilter = MessageType.Event,
    ) -> Subscription:
        """Call ``handler`` with a typed, parsed :class:`ParsedHarpMessage` each
        time the device emits a message for ``register``.

        By default only unsolicited ``Event`` messages are delivered. Pass
        ``message_types`` (a :class:`MessageType` or an iterable of them) to also
        observe ``Read``/``Write`` replies, e.g.
        ``message_types=(MessageType.Event, MessageType.Write)``.

        Handlers run on a single dedicated event thread, shared by *all*
        subscribers, so they may block or call back into :meth:`read`/:meth:`write`
        without deadlocking the reader or delaying synchronous requests. However,
        because that thread is shared, handlers are invoked **sequentially, in
        subscription order, one message at a time**: a slow handler delays every
        other subscriber and backs up later messages. Keep handlers quick, and
        offload heavy work to your own thread or queue.

        Returns a :class:`Subscription`; call :meth:`Subscription.unsubscribe` to
        stop.
        """
        sub = Subscription(self, register.address, handler, _normalize_message_types(message_types))
        with self._sub_lock:
            self._subscriptions.setdefault(register.address, []).append(sub)
            self._registers[register.address] = register
        return sub

    def subscribe_all(
        self,
        handler: Callable[[HarpMessage], None],
        *,
        message_types: MessageTypeFilter = MessageType.Event,
    ) -> Subscription:
        """Call ``handler`` with the raw :class:`HarpMessage` for every message,
        regardless of address, whose type is in ``message_types`` (default:
        ``Event`` only). Pass more types for a full-traffic firehose, e.g. a
        logger. See :meth:`subscribe` for threading and cancellation semantics."""
        sub = Subscription(self, None, handler, _normalize_message_types(message_types))
        with self._sub_lock:
            self._catch_all.append(sub)
        return sub

    def _remove_subscription(self, sub: "Subscription") -> None:
        with self._sub_lock:
            if sub._address is None:
                try:
                    self._catch_all.remove(sub)
                except ValueError:
                    pass
            else:
                subs = self._subscriptions.get(sub._address)
                if subs is not None:
                    try:
                        subs.remove(sub)
                    except ValueError:
                        pass
                    if not subs:
                        del self._subscriptions[sub._address]
                        self._registers.pop(sub._address, None)

    def _event_loop(self) -> None:
        while True:
            msg = self._event_queue.get()
            if msg is None:  # shutdown sentinel
                break
            self._deliver_event(msg)

    def _deliver_event(self, msg: HarpMessage) -> None:
        with self._sub_lock:
            subs = list(self._subscriptions.get(msg.address, ()))
            register = self._registers.get(msg.address)
            catch_all = list(self._catch_all)

        matching = [s for s in subs if msg.message_type in s._message_types]
        if matching and register is not None:
            try:
                parsed = ParsedHarpMessage.from_message(msg, register.parse(msg))
            except Exception:
                _logger.exception(
                    "Failed to parse %r for address 0x%02x", msg.message_type, msg.address
                )
            else:
                for sub in matching:
                    self._safe_call(sub._handler, parsed)

        for sub in catch_all:
            if msg.message_type in sub._message_types:
                self._safe_call(sub._handler, msg)

    @staticmethod
    def _safe_call(handler: Callable[[Any], None], arg: Any) -> None:
        try:
            handler(arg)
        except Exception:
            _logger.exception("Event handler %r raised", handler)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _read_loop(self) -> None:
        while self._running:
            try:
                chunk = self._transport.read()
            except TransportError:
                if self._running:
                    raise
                break  # expected while shutting down
            if not chunk:
                continue

            self._framer.feed(chunk)
            for msg in self._framer.frames():
                self._dispatch(msg)

    def _dispatch(self, msg: HarpMessage) -> None:
        # Fast path: correlate replies to a pending synchronous request. This is
        # O(1) and non-blocking, so it should never stall behind a slow subscriber.
        # Events are unsolicited and never correlate to requests
        if msg.message_type != MessageType.Event:
            with self._pending_lock:
                q = self._pending.get(msg.address)
            if q is not None:
                q.put(msg)

        self._event_queue.put(msg)

    def _request(self, address: int, frame: bytes) -> HarpMessage:
        q: queue.SimpleQueue = queue.SimpleQueue()
        with self._pending_lock:
            self._pending[address] = q
        try:
            self._transport.write(frame)
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
