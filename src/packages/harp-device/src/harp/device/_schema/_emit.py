import enum
import types
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Optional, Union, cast


import numpy as np
from typing_extensions import Sentinel
from pydantic_yaml import parse_yaml_raw_as
from harp.protocol import (
    AnonymousPayload,
    BitMask,
    BoolConverter,
    Converter,
    Field,
    GroupMask,
    HarpVersionConverter,
    IdentityConverter,
    RegisterBase,
    RegisterFloat,
    RegisterFloatArray,
    RegisterS8,
    RegisterS8Array,
    RegisterS16,
    RegisterS16Array,
    RegisterS32,
    RegisterS32Array,
    RegisterS64,
    RegisterS64Array,
    RegisterU8,
    RegisterU8Array,
    RegisterU16,
    RegisterU16Array,
    RegisterU32,
    RegisterU32Array,
    RegisterU64,
    RegisterU64Array,
    StringConverter,
    StructPayload,
    PayloadBase,
)
from harp.protocol import RESERVED_FIELD_NAMES
from harp.protocol import PayloadType as ProtoPayloadType

from ._model import DeviceModel, PayloadMember, PayloadType, Register, Registers, Visibility
from ._naming import enum_member_name, field_name

# Register base element: schema PayloadType -> numpy scalar type (byte size via np.dtype).
_ELEMENT: dict[PayloadType, type[np.generic]] = {
    PayloadType.U8: np.uint8,
    PayloadType.S8: np.int8,
    PayloadType.U16: np.uint16,
    PayloadType.S16: np.int16,
    PayloadType.U32: np.uint32,
    PayloadType.S32: np.int32,
    PayloadType.U64: np.uint64,
    PayloadType.S64: np.int64,
    PayloadType.Float: np.float32,
}
_SCALAR_REGISTER: dict[PayloadType, Any] = {
    PayloadType.U8: RegisterU8,
    PayloadType.S8: RegisterS8,
    PayloadType.U16: RegisterU16,
    PayloadType.S16: RegisterS16,
    PayloadType.U32: RegisterU32,
    PayloadType.S32: RegisterS32,
    PayloadType.U64: RegisterU64,
    PayloadType.S64: RegisterS64,
    PayloadType.Float: RegisterFloat,
}
_ARRAY_REGISTER: dict[PayloadType, Any] = {
    PayloadType.U8: RegisterU8Array,
    PayloadType.S8: RegisterS8Array,
    PayloadType.U16: RegisterU16Array,
    PayloadType.S16: RegisterS16Array,
    PayloadType.U32: RegisterU32Array,
    PayloadType.S32: RegisterS32Array,
    PayloadType.U64: RegisterU64Array,
    PayloadType.S64: RegisterS64Array,
    PayloadType.Float: RegisterFloatArray,
}


@dataclass(frozen=True)
class ConverterContext:
    """A payload value's schema definition, resolved against its register context.

    Handed to every converter factory so it can construct the converter with the
    right arguments — e.g. ``StringConverter(span)``, ``HarpVersionConverter(element)``,
    or ``IdentityConverter(dtype)``.
    """

    name: str  # yml field key ("__value__" for a whole-register value)
    interface_type: Optional[str]  # the DSL interfaceType (None = raw/native)
    mask: Optional[int]  # bit mask, when the value is bit-packed
    length: int  # element count this value spans (0 = unset -> scalar)
    element: np.dtype  # the register's base element dtype (from PayloadType)
    element_size: int  # the register's base element byte size

    @property
    def span(self) -> int:
        """Byte span of the value (element count * element size)."""
        return max(1, self.length) * self.element_size

    @property
    def member_dtype(self) -> np.dtype:
        """The value's own numpy dtype — a native primitive interfaceType overrides the element."""
        if self.interface_type is not None:
            entry = _INTERFACES.get(self.interface_type)
            if entry is not None and entry.native_dtype is not None:
                return np.dtype(entry.native_dtype)
        return self.element

    @property
    def raw_dtype(self) -> np.dtype:
        """Native passthrough dtype — a sub-array when the value spans >1 element."""
        if self.length > 1:
            return np.dtype((self.element.type, (self.length,)))
        return self.element


# A converter factory builds a converter from a field's DSL context.
ConverterFactory = Callable[[ConverterContext], Converter[Any]]
# A user-supplied converter: a ready instance, or a factory that builds one from context.
ConverterValue = Union[Converter[Any], ConverterFactory]
# Internal built-in factory — may decline (return None) when the DSL type doesn't
# actually fit (e.g. a primitive whose declared byte span isn't its native size).
_InterfaceFactory = Callable[[ConverterContext], Optional[Converter[Any]]]
# Coerces a field's yml numeric default into its typed value (``_NO_DEFAULT`` = skip).
_DefaultCoercer = Callable[[float, ConverterContext], Any]

_NO_DEFAULT = Sentinel("_NO_DEFAULT")  # this interface has no numeric default representation


def _numpy_default(value: float, ctx: ConverterContext) -> Any:
    literal = int(value) if value == np.floor(value) else value
    return np.dtype(ctx.member_dtype).type(literal)


def _bool_default(value: float, ctx: ConverterContext) -> Any:
    return bool(value != 0)


def _skip_default(value: float, ctx: ConverterContext) -> Any:
    return _NO_DEFAULT


def _native(dtype: type[np.generic]) -> _InterfaceFactory:
    # A native primitive decodes as an identity passthrough. Unmasked, it only fits
    # when its declared byte span matches its width; otherwise it declines (returns
    # None) and the field re-interprets the bytes via a custom ``{Field}Converter``.
    # Masked, it is always a native slice of the element (member_dtype == this width).
    d = np.dtype(dtype)
    return lambda ctx: (
        IdentityConverter(d) if ctx.mask is not None or ctx.span == d.itemsize else None
    )


@dataclass(frozen=True)
class _Interface:
    """A built-in interfaceType: how to build its converter, how to coerce its
    default value, and its native numpy dtype (fixed-width primitives only)."""

    build: _InterfaceFactory
    default: _DefaultCoercer
    native_dtype: Optional[type[np.generic]] = None


# Every interfaceType the library handles natively, in one uniform table: the
# fixed-width primitives (identity passthrough, carrying their numpy scalar as
# ``native_dtype``) beside string/bool/HarpVersion. Custom interfaceTypes are
# supplied by the caller (see ``converters=``).
_INTERFACES: dict[str, _Interface] = {
    "byte": _Interface(_native(np.uint8), _numpy_default, np.uint8),
    "sbyte": _Interface(_native(np.int8), _numpy_default, np.int8),
    "short": _Interface(_native(np.int16), _numpy_default, np.int16),
    "ushort": _Interface(_native(np.uint16), _numpy_default, np.uint16),
    "int": _Interface(_native(np.int32), _numpy_default, np.int32),
    "uint": _Interface(_native(np.uint32), _numpy_default, np.uint32),
    "long": _Interface(_native(np.int64), _numpy_default, np.int64),
    "ulong": _Interface(_native(np.uint64), _numpy_default, np.uint64),
    "float": _Interface(_native(np.float32), _numpy_default, np.float32),
    "string": _Interface(lambda ctx: StringConverter(ctx.span), _skip_default),
    "bool": _Interface(lambda ctx: BoolConverter(), _bool_default),
    "HarpVersion": _Interface(lambda ctx: HarpVersionConverter(ctx.element), _skip_default),
}


def _materialize(value: ConverterValue, ctx: ConverterContext) -> Converter[Any]:
    """A user converter value is either a ready instance or a ``(ctx) -> Converter`` factory."""
    return value if isinstance(value, Converter) else value(ctx)


class UnknownConverterError(ValueError):
    """A custom ``interfaceType`` needs a converter not found in ``converters=``."""


class NameCollisionError(ValueError):
    """Two schema identifiers collapse to one Python name, or one shadows a reserved name.

    Casing is not significant to the generator naming convention, so distinct yml
    keys (``DIO0`` / ``Dio0``) can converge — which would silently alias an enum
    member or drop a payload field.
    """


def _is_native(interface_type: Optional[str]) -> bool:
    """True when a value decodes as a native numpy passthrough: no interfaceType, or a
    fixed-width primitive one. Such a whole-register value needs no payload wrapper.
    """
    if interface_type is None:
        return True
    entry = _INTERFACES.get(interface_type)
    return entry is not None and entry.native_dtype is not None


def _new_class(name: str, bases: tuple, namespace: dict, kwds: Optional[dict] = None) -> type:
    return types.new_class(name, bases, kwds or {}, lambda ns: ns.update(namespace))


class _Emitter:
    def __init__(
        self,
        device: Union[DeviceModel, Registers],
        converters: Optional[Mapping[str, ConverterValue]],
        strict: bool,
        exclude_private: bool,
    ) -> None:
        self.device = device
        self.converters = dict(converters or {})
        self.strict = strict
        self.exclude_private = exclude_private
        self.group_masks = device.groupMasks or {}
        self.bit_masks = device.bitMasks or {}
        self.enums = self._build_enums()
        # Payload classes are cached by name so registers sharing an ``interfaceType``
        # share one class, as the generator's module-level payload list does.
        self.payloads: dict[str, type] = {}

    # -- naming -----------------------------------------------------------
    def _rename(
        self,
        kind: str,
        owner: str,
        keys: Iterable[str],
        convert: Callable[[str], str],
        reserved: bool = False,
    ) -> dict[str, str]:
        """Map yml keys to their Python names, rejecting collisions.

        Type-level names (registers, enums, payloads) stay verbatim; only enum
        members and payload fields are converted, so only those can collide.
        """
        renamed: dict[str, str] = {}
        origin: dict[str, str] = {}
        for key in keys:
            name = convert(key)
            clash = origin.get(name)
            if clash is not None:
                raise NameCollisionError(
                    f"{owner}: {kind}s {clash!r} and {key!r} both map to {name!r}; "
                    f"rename one in the schema"
                )
            if reserved and name in RESERVED_FIELD_NAMES:
                raise NameCollisionError(
                    f"{owner}: {kind} {key!r} maps to {name!r}, which is reserved by "
                    f"the payload base class; rename it in the schema"
                )
            origin[name] = key
            renamed[key] = name
        return renamed

    # -- enums ------------------------------------------------------------
    def _build_enums(self) -> dict[str, Any]:
        # Enum type names stay verbatim; members take the generator's SCREAMING_SNAKE.
        enums: dict[str, Any] = {}
        for name, spec in self.bit_masks.items():
            # IntFlag has no zero-valued member; drop it if present.
            bits = {k: v for k, v in spec.bits.items() if int(v) != 0}
            renamed = self._rename("bit", name, bits, enum_member_name)
            enums[name] = enum.IntFlag(name, {renamed[k]: int(v) for k, v in bits.items()})
        for name, spec in self.group_masks.items():
            renamed = self._rename("value", name, spec.values, enum_member_name)
            enums[name] = enum.IntEnum(name, {renamed[k]: int(v) for k, v in spec.values.items()})
        return enums

    # -- converter resolution (one uniform factory pipeline) -------------
    def _resolve_converter(self, ctx: ConverterContext) -> Converter[Any]:
        """Build the converter for a payload value from its schema context."""
        it = ctx.interface_type
        entry = _INTERFACES.get(it) if it is not None else None
        if entry is not None:
            converter = entry.build(ctx)
            if converter is not None:
                return converter
        if ctx.mask is not None:
            return IdentityConverter(ctx.member_dtype)  # bit-field: native slice of the element
        if it is None:
            return IdentityConverter(ctx.raw_dtype)  # raw passthrough / sub-array
        # A known primitive that didn't fit is re-interpreted per field (``{Name}Converter``);
        # an unknown interfaceType is a domain type (``{InterfaceType}Converter``).
        symbol = f"{ctx.name}Converter" if entry is not None else f"{it}Converter"
        return self._extension(symbol, ctx)

    def _extension(self, symbol: str, ctx: ConverterContext) -> Converter[Any]:
        value = self.converters.get(symbol)
        if value is not None:
            return _materialize(value, ctx)
        if not self.strict:
            return IdentityConverter(ctx.element)
        raise UnknownConverterError(
            f"no converter {symbol!r} in converters=; pass "
            f"converters={{{symbol!r}: <Converter or (ctx) -> Converter>}} "
            f"or strict=False to decode as the native type"
        )

    # -- defaults ---------------------------------------------------------
    def _default(self, member: PayloadMember, type_name: str, ctx: ConverterContext) -> Any:
        """The field's typed default value, or ``_NO_DEFAULT`` when it has none."""
        _default_value = member.defaultValue if member.defaultValue is not None else member.minValue
        if _default_value is None or (member.length or 0) > 1:
            return _NO_DEFAULT
        value = float(_default_value.root)
        if type_name in self.group_masks:
            e = self.enums[type_name]
            for mv in self.group_masks[type_name].values.values():
                if int(mv) == int(value):
                    return e(int(value))
            return int(value)
        if member.converter is not None:
            return _NO_DEFAULT  # a custom converter owns its own decoding; no numeric default
        it = ctx.interface_type
        entry = _INTERFACES.get(it) if it is not None else None
        if entry is not None:
            return entry.default(value, ctx)
        if it is None:
            return _numpy_default(value, ctx)  # raw native passthrough
        return _NO_DEFAULT  # custom domain interfaceType: no numeric default

    # -- fields -----------------------------------------------------------
    def _build_field(self, key: str, member: PayloadMember, reg: Register) -> Any:
        # ``key`` stays the verbatim yml name: it feeds ``ConverterContext.name``, and
        # a custom converter symbol is derived from the pre-rename key ("Data" ->
        # "DataConverter"). The renamed attribute name is applied by the caller.
        elem_np = _ELEMENT[reg.type]
        elem_size = np.dtype(elem_np).itemsize
        offset = member.offset or 0
        it = member.interfaceType.root if member.interfaceType else None
        type_name = it or (member.maskType.root if member.maskType else "")
        ctx = ConverterContext(
            name=key,
            interface_type=it,
            mask=member.mask,
            length=member.length or 0,
            element=np.dtype(elem_np),
            element_size=elem_size,
        )
        default = self._default(member, type_name, ctx)
        default_kwarg = {} if default is _NO_DEFAULT else {"default": default}

        # A group mask is an enum sub-field descriptor, not a Field(converter).
        if type_name in self.group_masks:
            full = (1 << (elem_size * 8)) - 1
            mask = member.mask if member.mask is not None else full
            return GroupMask(enum=self.enums[type_name], mask=mask, offset=offset, **default_kwarg)

        field_kwargs: dict[str, Any] = {"offset": offset, **default_kwarg}
        if member.mask is not None:
            field_kwargs["mask"] = member.mask
        return Field(self._resolve_converter(ctx), **field_kwargs)

    # -- payloads ---------------------------------------------------------
    def _payload_name(self, name: str, reg: Register) -> str:
        """The payload class name: the ``interfaceType`` when a structured register
        declares one (so registers sharing that type share a class), else
        ``{Register}Payload``."""
        it = reg.interfaceType.root if reg.interfaceType else None
        if reg.payloadSpec is not None and it:
            return it
        return f"{name}Payload"

    def _build_payload(self, name: str, reg: Register) -> type:
        payload_name = self._payload_name(name, reg)
        cached = cast(type[PayloadBase[Any]], self.payloads.get(payload_name))
        if cached is not None:
            # Reuse is keyed on the name alone (as the generator's payload list is), so
            # refuse to hand back a class whose layout can't describe this register.
            if cached.dtype.itemsize != np.dtype(_ELEMENT[reg.type]).itemsize * (reg.length or 1):
                raise NameCollisionError(
                    f"{name}: interfaceType {payload_name!r} is already used by a payload "
                    f"of a different size; the two registers cannot share one payload class"
                )
            return cached
        payload = self._new_payload(payload_name, reg)
        self.payloads[payload_name] = payload
        return payload

    def _new_payload(self, name: str, reg: Register) -> type:
        elem_np = _ELEMENT[reg.type]
        elem_size = np.dtype(elem_np).itemsize
        length = reg.length or 1

        if reg.payloadSpec is not None:
            renamed = self._rename("field", name, reg.payloadSpec, field_name, reserved=True)
            namespace = {
                renamed[key]: self._build_field(key, member, reg)
                for key, member in reg.payloadSpec.items()
            }
            kwds = {"length": length} if length > 1 else {}
            return _new_class(name, (StructPayload[elem_np],), namespace, kwds)

        # anonymous single-value payload
        mt = reg.maskType.root if reg.maskType else None
        it = reg.interfaceType.root if reg.interfaceType else None
        if mt in self.group_masks:
            full = (1 << (elem_size * 8)) - 1
            descriptor: Any = GroupMask(enum=self.enums[mt], mask=full)
        elif mt in self.bit_masks:
            descriptor = BitMask(enum=self.enums[mt])
        else:
            assert it is not None, (
                f"{name}: register needs a payloadSpec, maskType, or interfaceType"
            )
            ctx = ConverterContext(
                name="__value__",
                interface_type=it,
                mask=None,
                length=length,
                element=np.dtype(elem_np),
                element_size=elem_size,
            )
            descriptor = Field(self._resolve_converter(ctx))
        return _new_class(name, (AnonymousPayload[elem_np],), {"__value__": descriptor})

    # -- registers --------------------------------------------------------
    def _class_name(self, name: str, reg: Register) -> str:
        """A private register's class is underscore-prefixed; its payload class is not."""
        return f"_{name}" if reg.visibility is Visibility.private else name

    def _build_register(self, name: str, class_name: str, reg: Register) -> type[RegisterBase[Any]]:
        length = reg.length or 1
        it = reg.interfaceType.root if reg.interfaceType else None

        # A plain scalar/array register needs no payload wrapper: its whole value is a
        # native passthrough (no payloadSpec, no maskType, no custom converter).
        if (
            reg.payloadSpec is None
            and reg.maskType is None
            and reg.converter is None
            and _is_native(it)
        ):
            if length > 1:  # plain array register
                cls = _ARRAY_REGISTER[reg.type](reg.address, length=length)
                cls.__name__ = cls.__qualname__ = class_name
                return cls
            return _new_class(class_name, (_SCALAR_REGISTER[reg.type],), {"address": reg.address})

        payload_cls = self._build_payload(name, reg)
        return _new_class(
            class_name,
            (RegisterBase,),
            {
                "address": reg.address,
                "payload_type": ProtoPayloadType[reg.type.name],
                "payload_class": payload_cls,
            },
        )

    def emit(self) -> dict[str, type[RegisterBase[Any]]]:
        emitted: dict[str, type[RegisterBase[Any]]] = {}
        for name, reg in self.device.registers.items():
            if self.exclude_private and reg.visibility is Visibility.private:
                continue
            class_name = self._class_name(name, reg)
            emitted[class_name] = self._build_register(name, class_name, reg)
        return emitted


def parse_device_schema(text: str) -> DeviceModel:
    """Parse a Harp ``device.yml`` (or a header-less fragment) into a :class:`DeviceModel`.

    A header-less fragment (just ``registers`` / ``bitMasks`` / ``groupMasks``)
    parses fine — the identity fields (``device`` / ``whoAmI`` / ...) are simply
    ``None``. Read files yourself, e.g.
    ``parse_device_schema(Path("device.yml").read_text())``.

    Uses ``pydantic-yaml`` (ruamel-backed, YAML 1.2), so group-mask keys like
    ``Off`` / ``On`` stay strings instead of being coerced to booleans.
    """
    return parse_yaml_raw_as(DeviceModel, text)


def create_registers(
    source: Union[str, DeviceModel, Registers],
    *,
    converters: Optional[Mapping[str, ConverterValue]] = None,
    strict: bool = True,
    exclude_private: bool = False,
) -> dict[str, type[RegisterBase[Any]]]:
    """Emit runtime register classes from a device schema.

    ``source`` is yaml text or an already-parsed :class:`DeviceModel` /
    :class:`Registers`. Identifiers follow the same conventions as the statically
    generated device packages: register, enum, and payload class names stay verbatim
    from the yml, while payload fields become ``snake_case`` and enum members
    ``SCREAMING_SNAKE_CASE``. ``converters`` supplies custom converters keyed by
    symbol name (e.g. ``{"DataConverter": ...}``); a value is either a ready
    :class:`~harp.protocol.Converter` instance or a factory
    ``(ctx: ConverterContext) -> Converter`` that builds one from the field's DSL
    context. A custom type with no matching converter raises
    ``UnknownConverterError`` when ``strict`` (the default); ``strict=False``
    decodes it as its native element type instead. ``exclude_private=True`` drops
    registers whose DSL ``visibility`` is ``private``; when kept, a private register's
    class is underscore-prefixed (``_Reserved0``). Note that the converter symbol for a
    payload field derives from its *verbatim* yml key, not the renamed field.
    """
    device = source if isinstance(source, Registers) else parse_device_schema(source)
    return _Emitter(device, converters, strict, exclude_private).emit()
