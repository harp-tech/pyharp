"""Transport-agnostic Harp device base class."""

import logging
import queue
import threading
from collections.abc import Callable, Iterable
from typing import Any, ClassVar, Self, TypeVar

from harp.protocol import HarpMessage, MessageType
from harp.protocol._message import ParsedHarpMessage
from harp.protocol._register import RegisterBase

from ._core_registers import CORE_REGISTERS, CoreRegistersNamespace
from ._framer import HarpFramer
from ._registers import (
    WhoAmI,
)
from ._transport import ITransport, TransportError

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


class _RegisterAccessor:
    """Read-only descriptor backing :attr:`Device.registers`.

    It defines ``__get__`` but no ``__set__``, which is deliberate:

    * ``device.registers`` is **read-only** — assigning to it is a type error;
    * a subclass may **narrow** the attribute by redeclaring it, because a
      read-only member is checked *covariantly* (a mutable one would be invariant).

    So a statically generated device can redeclare
    ``registers: ClassVar[<CoreRegistersNamespace subclass>]`` to type
    ``device.registers.<Name>`` precisely, with **no**
    ``reportIncompatibleVariableOverride`` suppression. The real namespace is
    assigned per subclass in :meth:`Device.__init_subclass__` (which shadows this
    descriptor); this default only backs the bare :class:`Device` base.
    """

    def __get__(self, obj: object, owner: type | None = None) -> CoreRegistersNamespace:
        return CoreRegistersNamespace(CORE_REGISTERS)


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


class Device:
    """Harp device protocol logic (framing, request/reply, register access)
    over an :class:`~harp.device.ITransport`.

    Must be opened before use, via ``with`` or :meth:`open`. A subclass declares its
    device-specific registers in :attr:`__REGISTERS__` and sets :attr:`__whoami__` to
    validate device identity on open (``0x0`` skips the check). Registers are reached
    by name through :attr:`registers` (``device.registers.WhoAmI``).

    Only :attr:`__REGISTERS__` and :attr:`__whoami__` are meant to be set by a
    subclass; the base owns the protocol methods and the register-namespace derivation.
    """

    # === The following are class variables meant to be set by a subclass ===

    #: Expected ``WhoAmI`` of the device this class models; ``0x0`` skips the check.
    __whoami__: ClassVar[int] = 0x0

    #: The device's own registers. A subclass sets this to a tuple of register
    #: classes; the common Harp registers are merged in automatically.
    __REGISTERS__: ClassVar[tuple[type[RegisterBase[Any]], ...]] = ()

    #: Name-indexed, **read-only** view of all this device's registers (core +
    #: ``__REGISTERS__``). Reach a register by name (``device.registers.WhoAmI`` —
    #: the common registers autocomplete on any device), or use
    #: ``device.registers.by_address``; see :class:`~harp.device.RegisterNamespace`.
    #: A statically generated device may *narrow* this by redeclaring
    #: ``registers: ClassVar[<CoreRegistersNamespace subclass>]`` for typed, autocompleting
    registers = _RegisterAccessor()

    REPLY_TIMEOUT: ClassVar[float] = 5.0  # seconds

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Merge inherited registers (core + any parent's) with this class's own
        # __REGISTERS__; on an address clash the device's register wins.
        merged: dict[int, type[RegisterBase[Any]]] = dict(cls.registers.by_address)
        for register in cls.__dict__.get("__REGISTERS__", ()):
            merged[register.address] = register
        # ``type.__setattr__`` (not ``cls.registers = ...``) keeps pyright treating
        # ``registers`` as read-only; it shadows the base descriptor on the subclass.
        type.__setattr__(cls, "registers", CoreRegistersNamespace(merged.values()))

    def __init__(self, transport: ITransport, *, raise_on_error: bool = True) -> None:
        self._transport = transport
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
