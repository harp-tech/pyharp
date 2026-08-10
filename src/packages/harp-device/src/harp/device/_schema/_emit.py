import enum
import types
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Union

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
)
from harp.protocol import PayloadType as ProtoPayloadType

from ._model import DeviceModel, PayloadMember, PayloadType, Register, Registers, Visibility

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

    # -- enums ------------------------------------------------------------
    def _build_enums(self) -> dict[str, Any]:
        # Enum names and members are kept verbatim from the yml.
        enums: dict[str, Any] = {}
        for name, spec in self.bit_masks.items():
            # IntFlag has no zero-valued member; drop it if present.
            members = {k: int(v) for k, v in spec.bits.items() if int(v) != 0}
            enums[name] = enum.IntFlag(name, members)
        for name, spec in self.group_masks.items():
            members = {k: int(v) for k, v in spec.values.items()}
            enums[name] = enum.IntEnum(name, members)
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
    def _build_field(self, key: str, member: PayloadMember, reg: Register) -> tuple[str, Any]:
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
            return key, GroupMask(
                enum=self.enums[type_name], mask=mask, offset=offset, **default_kwarg
            )

        field_kwargs: dict[str, Any] = {"offset": offset, **default_kwarg}
        if member.mask is not None:
            field_kwargs["mask"] = member.mask
        return key, Field(self._resolve_converter(ctx), **field_kwargs)

    # -- payloads ---------------------------------------------------------
    def _build_payload(self, name: str, reg: Register) -> type:
        elem_np = _ELEMENT[reg.type]
        elem_size = np.dtype(elem_np).itemsize
        length = reg.length or 1

        if reg.payloadSpec is not None:
            namespace = {}
            for key, member in reg.payloadSpec.items():
                fname, descriptor = self._build_field(key, member, reg)
                namespace[fname] = descriptor
            kwds = {"length": length} if length > 1 else {}
            return _new_class(f"{name}Payload", (StructPayload[elem_np],), namespace, kwds)

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
        return _new_class(f"{name}Payload", (AnonymousPayload[elem_np],), {"__value__": descriptor})

    # -- registers --------------------------------------------------------
    def _build_register(self, name: str, reg: Register) -> type[RegisterBase[Any]]:
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
                cls.__name__ = cls.__qualname__ = name
                return cls
            return _new_class(name, (_SCALAR_REGISTER[reg.type],), {"address": reg.address})

        payload_cls = self._build_payload(name, reg)
        return _new_class(
            name,
            (RegisterBase,),
            {
                "address": reg.address,
                "payload_type": ProtoPayloadType[reg.type.name],
                "payload_class": payload_cls,
            },
        )

    def emit(self) -> dict[str, type[RegisterBase[Any]]]:
        return {
            name: self._build_register(name, reg)
            for name, reg in self.device.registers.items()
            if not (self.exclude_private and reg.visibility is Visibility.private)
        }


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
    :class:`Registers`. Identifiers (fields, enum members) are
    kept verbatim from the yml. ``converters`` supplies custom converters keyed by
    symbol name (e.g. ``{"DataConverter": ...}``); a value is either a ready
    :class:`~harp.protocol.Converter` instance or a factory
    ``(ctx: ConverterContext) -> Converter`` that builds one from the field's DSL
    context. A custom type with no matching converter raises
    ``UnknownConverterError`` when ``strict`` (the default); ``strict=False``
    decodes it as its native element type instead. ``exclude_private=True`` drops
    registers whose DSL ``visibility`` is ``private``.
    """
    device = source if isinstance(source, Registers) else parse_device_schema(source)
    return _Emitter(device, converters, strict, exclude_private).emit()
