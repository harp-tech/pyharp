from typing import TYPE_CHECKING, Any, TypeVar

try:
    import reactivex as rx
    import reactivex.operators as ops
    from reactivex.disposable import Disposable
except ModuleNotFoundError as exc:
    raise ImportError(
        "harp.device.rx requires the 'reactivex' package, which is not installed. "
        "Install the optional extra with:  pip install 'harp-device[rx]'."
    ) from exc

from harp.protocol import HarpMessage, MessageType
from harp.protocol._message import ParsedHarpMessage
from harp.protocol._register import RegisterBase

from ._device import MessageTypeFilter

if TYPE_CHECKING:
    from ._device import Device

P = TypeVar("P")

__all__ = ["observe", "observe_all"]


def observe(
    device: "Device",
    register: type[RegisterBase[P]],
    *,
    message_types: MessageTypeFilter = MessageType.Event,
) -> "rx.Observable[ParsedHarpMessage[P]]":
    """Return a hot, multicast Observable of parsed messages for ``register``.

    Mirrors :meth:`Device.subscribe`: by default only ``Event`` messages are
    emitted; pass ``message_types`` for read/write replies too.

    The stream is ref-counted (``ops.share``): the *first* subscriber creates a
    single underlying :meth:`Device.subscribe`, additional subscribers share it,
    and the device subscription is disposed once the last one unsubscribes.

    Note: emissions run on the device's shared event thread. Use
    ``ops.observe_on(scheduler)`` to move heavy downstream work off it.
    """

    def on_subscribe(observer: "rx.abc.ObserverBase[Any]", _: Any = None) -> Disposable:
        sub = device.subscribe(register, observer.on_next, message_types=message_types)
        return Disposable(sub.unsubscribe)

    return rx.create(on_subscribe).pipe(ops.share())


def observe_all(
    device: "Device",
    *,
    message_types: MessageTypeFilter = MessageType.Event,
) -> "rx.Observable[HarpMessage]":
    """Return a hot, multicast Observable of raw messages for *every* address.

    Mirrors :meth:`Device.subscribe_all` (a full-traffic firehose when passed
    more message types). Same ref-counted, hot, single-underlying-subscription
    lifecycle and threading semantics as :func:`observe`.
    """

    def on_subscribe(observer: "rx.abc.ObserverBase[Any]", _: Any = None) -> Disposable:
        sub = device.subscribe_all(observer.on_next, message_types=message_types)
        return Disposable(sub.unsubscribe)

    return rx.create(on_subscribe).pipe(ops.share())
