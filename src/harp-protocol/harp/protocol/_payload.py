import enum
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Protocol,
    TypeVar,
    final,
    get_args,
    overload,
)

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from typing_extensions import Self, Sentinel, dataclass_transform

from ._payload_converters import Converter as _Converter
from ._payload_converters import IdentityConverter as _IdentityConverter

NpStructT = TypeVar("NpStructT", bound=np.generic)
T = TypeVar("T")
E = TypeVar("E", bound=enum.IntEnum)

_MISSING = Sentinel("_MISSING")
_DEFAULT_ELEMENT = np.dtype(np.uint8)


@dataclass(frozen=True)
class _FieldSlot:
    """One physical numpy field: its dtype and byte offset within the record."""

    dtype: np.dtype
    byte_offset: int


def _mask_trailing_zeros(mask: int) -> int:
    """Number of trailing zero bits in ``mask`` — the right-shift that aligns a
    masked field to bit 0."""
    if mask == 0:
        return 0
    return (mask & -mask).bit_length() - 1


# ---------------------------------------------------------------------------
# Descriptors — scalar variants (return Python / 0-D types)
# ---------------------------------------------------------------------------


class Field(Generic[T]):
    """Descriptor for a whole-element (or reinterpreted multi-element) payload view.

    The view reads ``converter.dtype.itemsize`` bytes starting at ``offset`` (in
    base-element units; see :class:`StructPayload`) and runs them through
    ``converter``. The converter owns its own ``dtype`` (byte layout) and is
    independent of the payload's base element type, so the same converter works
    under any register width.

    ``offset`` defaults to ``0``. Omitting it suits a payload with a single
    member; when a payload has several distinct slots, each must declare an
    explicit ``offset=`` or the overlap check rejects the layout.
    """

    if TYPE_CHECKING:
        # Makes `field: T = Field(converter=...)` valid under @dataclass_transform without a
        # type-mismatch error. At runtime __new__ is not defined and a Field instance is
        # returned as normal.
        def __new__(  # type: ignore[misc]
            cls, converter: "_Converter[T]", *, offset: int = 0, default: "T" = ...
        ) -> "T": ...

    def __init__(
        self, converter: _Converter[T], *, offset: int = 0, default: object = _MISSING
    ) -> None:
        self._converter = converter
        self._name: str | None = None
        self._offset = offset
        self._default = default

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: object = None) -> "Field[T]": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> T: ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        return self._converter.decode_scalar(obj._arr[self._name])

    def _to_batch(self) -> "_FieldBatch[T]":
        return _FieldBatch(converter=self._converter)


class BitFlag:
    """Descriptor for a single bit within a payload element, exposed as ``bool``.

    Reads the base element at ``offset`` (base-element units; defaults to ``0``)
    and tests ``element & mask``. The element width and the physical storage slot
    are derived from the payload's base element type, so several bit flags at the
    same offset automatically share storage.
    """

    if TYPE_CHECKING:

        def __new__(
            cls, *, mask: int, offset: int = 0, default: bool = ...
        ) -> bool: ...  # type: ignore[misc]  # noqa: E704

    def __init__(self, *, mask: int, offset: int = 0, default: object = _MISSING) -> None:
        self._mask = mask
        self._offset = offset
        self._default = default
        # Derived in PayloadBase.__init_subclass__:
        self._slot: str = "value"
        self._dtype: np.dtype = _DEFAULT_ELEMENT

    @overload
    def __get__(self, obj: None, owner: object = None) -> "BitFlag": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> bool: ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        return bool(obj._arr[self._slot] & self._mask)

    def _to_batch(self) -> "_BitFlagBatch":
        return _BitFlagBatch(self._mask, slot=self._slot, dtype=self._dtype)


def _build_enum_lookup(enum_cls: type) -> "tuple[list[str], np.ndarray]":
    """Helper for GroupMask to build the category list and code lookup table for a given enum.IntEnum class."""
    members = list(enum_cls)
    categories = [m.name for m in members]
    max_val = max(int(m) for m in members)
    code_dtype = np.int8 if len(members) < 128 else np.int32
    code_lookup = np.full(max_val + 1, -1, dtype=code_dtype)
    for code, m in enumerate(members):
        code_lookup[int(m)] = code
    return categories, code_lookup


class GroupMask(Generic[E]):
    """Descriptor for a masked, shifted sub-field of a payload element.

    The raw value is extracted as ``(element & mask) >> shift`` and then mapped:

    * ``enum=`` — to an ``enum.IntEnum`` member (strict; unknown code raises);
    * ``converter=`` — through a :class:`Converter` applied to the *masked*
      integer (numeric casts, bool, custom);
    * neither — returned as the raw masked numpy integer (the element's dtype).

    The right-shift is always derived from ``mask`` (its trailing-zero count, so the
    field aligns to bit 0); ``offset`` defaults to ``0``. The element width and
    storage slot are derived from the payload's base element type, so several masked
    fields at the same offset share storage automatically.
    """

    if TYPE_CHECKING:
        # enum variant -> the field type is the enum
        @overload
        def __new__(  # type: ignore[misc]  # noqa: E704
            cls, *, mask: int, enum: "type[E]", offset: int = 0, default: "E" = ...
        ) -> "E": ...
        # converter variant -> the field type is the converter's output type
        @overload
        def __new__(  # type: ignore[misc]  # noqa: E704
            cls, *, mask: int, converter: "_Converter[T]", offset: int = 0, default: "T" = ...
        ) -> "T": ...
        # raw variant -> a plain integer
        @overload
        def __new__(  # type: ignore[misc]  # noqa: E704
            cls, *, mask: int, offset: int = 0, default: int = ...
        ) -> int: ...
        def __new__(cls, **kwargs: Any) -> Any: ...  # type: ignore[misc]  # noqa: E704

    def __init__(
        self,
        *,
        mask: int,
        enum: type[E] | None = None,
        converter: "_Converter[Any] | None" = None,
        offset: int = 0,
        default: object = _MISSING,
    ) -> None:
        if enum is not None and converter is not None:
            raise TypeError("GroupMask accepts at most one of 'enum' or 'converter'")
        self._mask = mask
        self._shift = _mask_trailing_zeros(mask)
        self._enum = enum
        self._converter = converter
        self._offset = offset
        self._default = default
        # Derived in PayloadBase.__init_subclass__:
        self._slot: str = "value"
        self._dtype: np.dtype = _DEFAULT_ELEMENT
        if enum is not None:
            self._categories, self._code_lookup = _build_enum_lookup(enum)
        else:
            self._categories, self._code_lookup = None, None

    def _decode_raw(self, raw: Any) -> Any:
        """Map an extracted (already masked + shifted) integer to its value."""
        if self._enum is not None:
            return self._enum(int(raw))
        if self._converter is not None:
            return self._converter.decode_scalar(self._converter.dtype.type(raw))
        return raw

    def _encode_value(self, value: Any) -> int:
        """Map a user value back to the integer to be masked + shifted into the slot."""
        if self._converter is not None and self._enum is None:
            tmp = np.zeros((), dtype=self._converter.dtype)
            self._converter.encode_into(tmp, value)
            return int(tmp)
        return int(value)

    @overload
    def __get__(self, obj: None, owner: object = None) -> "GroupMask[E]": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> E: ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        raw = (obj._arr[self._slot] & self._mask) >> self._shift
        return self._decode_raw(raw)

    def _to_batch(self) -> "_GroupMaskBatch[E]":
        return _GroupMaskBatch(
            self._mask,
            self._enum,
            converter=self._converter,
            slot=self._slot,
            dtype=self._dtype,
        )


# ---------------------------------------------------------------------------
# Descriptors — batch variants (return ndarray views)
# These are mostly used for batch operations like `to_dataframe`
# ---------------------------------------------------------------------------


class _FieldBatch(Generic[T]):
    """Same as _Field but returns an NDArray view for batch payloads rather than a scalar value."""

    def __init__(self, *, converter: _Converter[T]) -> None:
        self._converter = converter
        self._name: str | None = None

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    @overload
    def __get__(self, obj: None, owner: object = None) -> "_FieldBatch[T]": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> "NDArray[Any]": ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        return self._converter.decode_batch(obj._arr[self._name])


class _BitFlagBatch:
    """Same as _BitFlag but returns an NDArray view for batch payloads rather than a scalar value."""

    def __init__(
        self,
        mask: int,
        *,
        slot: str = "value",
        dtype: "np.dtype | str | type" = np.uint8,
    ) -> None:
        self._mask = mask
        self._slot = slot
        self._dtype = np.dtype(dtype)

    @overload
    def __get__(self, obj: None, owner: object = None) -> "_BitFlagBatch": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> "NDArray[np.bool_]": ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        return (obj._arr[self._slot] & self._mask) != 0


class _GroupMaskBatch(Generic[E]):
    """Same as GroupMask but returns an NDArray view for batch payloads rather than a scalar value."""

    def __init__(
        self,
        mask: int,
        enum: type[E] | None,
        *,
        converter: "_Converter[Any] | None" = None,
        slot: str = "value",
        dtype: "np.dtype | str | type" = np.uint8,
    ) -> None:
        self._mask = mask
        self._shift = _mask_trailing_zeros(mask)
        self._enum = enum
        self._converter = converter
        self._slot = slot
        self._dtype = np.dtype(dtype)
        if enum is not None:
            self._categories, self._code_lookup = _build_enum_lookup(enum)
        else:
            self._categories, self._code_lookup = None, None

    @overload
    def __get__(self, obj: None, owner: object = None) -> "_GroupMaskBatch[E]": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> "NDArray[Any]": ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        raw = (obj._arr[self._slot] & self._mask) >> self._shift
        # Enum batches return raw integer codes (see to_dataframe for Categorical
        # decoding). Converter batches decode element-wise; raw stays integer.
        if self._enum is None and self._converter is not None:
            return self._converter.decode_batch(raw.astype(self._converter.dtype))
        return raw


_PT = TypeVar("_PT", bound="PayloadBase[Any]")
_MISSING_INIT = Sentinel("_MISSING_INIT")


class Batch(Protocol[_PT]):
    """Alias type for batched payloads so we can have nice type-hinting
    for batch operations like `read_frames` and `to_dataframe`.

    Statically, ``Batch[P]`` is a distinct type from ``P`` so the type
    checker knows ``read_frames`` returns an ndarray-shaped view rather
    than a single record. At runtime, the value is the auto-derived
    ``P.Batch`` sibling whose descriptors return ``NDArray`` views.

    Per-field dtype precision is intentionally dropped — every declared
    field reports ``NDArray[Any]`` — to keep ``RegisterBase[P]``
    parameterized by a single TypeVar.
    """

    raw_payload: "NDArray[Any]"
    value: "NDArray[Any]"

    def __len__(self) -> int: ...  # type: ignore[empty-body]

    def to_dataframe(self, *, decode_enums: bool = True) -> "pd.DataFrame": ...  # type: ignore[empty-body]

    def __getattr__(self, name: str) -> "NDArray[Any]": ...  # type: ignore[empty-body]


# Helpers for type checking using isinstance()
_SCALAR_DECLARATION_TYPES = (Field, BitFlag, GroupMask)
_BATCH_DECLARATION_TYPES = (_FieldBatch, _BitFlagBatch, _GroupMaskBatch)
_DECLARATION_TYPES = _SCALAR_DECLARATION_TYPES + _BATCH_DECLARATION_TYPES
_BITFIELD_TYPES = (BitFlag, GroupMask, _BitFlagBatch, _GroupMaskBatch)
_FIELD_TYPES = (Field, _FieldBatch)
_GROUP_MASK_TYPES = (GroupMask, _GroupMaskBatch)
_BIT_FLAG_TYPES = (BitFlag, _BitFlagBatch)

# value/raw_payload deliberately omitted: overriding them is the intended
# pattern for single-slot converter-driven payloads.
_RESERVED_FIELD_NAMES = frozenset({"_arr", "_dtype", "_repr_fields", "Batch"})


def _batch_init_disabled(self: "PayloadBase", *args: object, **kwargs: object) -> None:
    raise TypeError(
        f"{type(self).__name__} is a Batch payload; construct it via "
        f"from_array()/from_buffer() (or use its scalar twin "
        f"{type(self)._scalar_cls.__name__!s})."
    )


def _resolve_element_dtype(cls: type) -> np.dtype:
    """Resolve the base element dtype from the ``StructPayload[...]`` type arg.

    Only used for offset→byte arithmetic and the masked-read integer width.
    Defaults to uint8 (byte) when the payload is not parameterized, which makes
    byte-offset layouts of heterogeneous consecutive fields work out of the box.
    """
    for base in getattr(cls, "__orig_bases__", ()):
        for arg in get_args(base):
            if isinstance(arg, TypeVar):
                continue
            try:
                return np.dtype(arg)
            except TypeError:
                continue
    return _DEFAULT_ELEMENT


def _validate_mask_fits(cls: type, name: str, mask: int, elem: np.dtype) -> None:
    if mask < 0 or mask >= (1 << (elem.itemsize * 8)):
        raise TypeError(
            f"{cls.__name__}: mask {mask:#x} on {name!r} does not fit the base "
            f"element {elem} ({elem.itemsize} byte(s))"
        )


def _validate_no_overlap(cls: type, slots: "dict[str, _FieldSlot]", itemsize: int) -> None:
    """Validate that declared fields do not overlap and fit within the payload itemsize. Overlap is only
    allowed for masked fields sharing the same slot."""
    spans = sorted(
        (slot.byte_offset, slot.byte_offset + slot.dtype.itemsize, name)
        for name, slot in slots.items()
    )
    for start, end, name in spans:
        if end > itemsize:
            raise TypeError(
                f"{cls.__name__}: field {name!r} ends at byte {end}, beyond itemsize "
                f"{itemsize}; declare an explicit length="
            )
    for (prev_start, prev_end, prev_name), (start, end, name) in zip(spans, spans[1:]):
        if start < prev_end:
            raise TypeError(
                f"{cls.__name__}: fields {prev_name!r} and {name!r} overlap "
                f"(bytes [{prev_start},{prev_end}) vs [{start},{end})); masked sub-fields "
                f"of the same element must share an offset"
            )


def _build_struct_dtype(
    cls: type,
    declarations: "list[tuple[str, Field | BitFlag | GroupMask]]",
    length: int | None,
) -> np.dtype:
    """Build the numpy structured dtype from field declarations."""
    elem = cls._elem_dtype
    elem_size = elem.itemsize
    slots: dict[str, _FieldSlot] = {}
    mask_slot_by_byte_offset: dict[int, str] = {}

    for attr_name, val in declarations:
        byte_offset = val._offset * elem_size
        if isinstance(val, (BitFlag, GroupMask)):
            val._dtype = elem
            _validate_mask_fits(cls, attr_name, val._mask, elem)
            shared_slot = mask_slot_by_byte_offset.get(byte_offset)
            if shared_slot is not None:
                val._slot = shared_slot
            else:
                mask_slot_by_byte_offset[byte_offset] = attr_name
                val._slot = attr_name
                slots[attr_name] = _FieldSlot(elem, byte_offset)
        else:  # Field
            field_dtype = val._converter.dtype
            if attr_name in slots:
                raise TypeError(f"{cls.__name__}: duplicate field name {attr_name!r}")
            slots[attr_name] = _FieldSlot(field_dtype, byte_offset)

    if length is not None:
        itemsize = length * elem_size
    else:
        itemsize = max(slot.byte_offset + slot.dtype.itemsize for slot in slots.values())
    _validate_no_overlap(cls, slots, itemsize)
    return np.dtype(
        {
            "names": list(slots),
            "formats": [slot.dtype for slot in slots.values()],
            "offsets": [slot.byte_offset for slot in slots.values()],
            "itemsize": itemsize,
        }
    )


def _resolve_single_member(cls: type, declarations: "list[tuple[str, Any]]") -> "str | None":
    """A payload with exactly one full-span ``Field`` unwraps to that member on
    ``parse`` (register-level ``interfaceType``), avoiding a ``.value`` hop."""
    if len(declarations) != 1:
        return None
    attr, val = declarations[0]
    if isinstance(val, Field) and val._converter.dtype.itemsize == cls.dtype.itemsize:  # type: ignore[attr-defined]
        return attr
    return None


class PayloadBase(Generic[NpStructT]):
    """Base class for typed Harp register payloads.

    A subclass declares fields via the scalar descriptors above.
    ``__init_subclass__`` auto-derives a ``Batch`` sibling subclass with the
    same dtype but each descriptor swapped to a Batch variant returning an
    ``NDArray`` view. ``from_array`` routes by ``ndim`` so callers never need
    to mention the Batch class explicitly: 0-D records stay scalar, 1-D
    buffers become Batch.
    """

    # Structured numpy dtype describing the memory layout of a single payload record.
    dtype: ClassVar[np.dtype]
    # Field names shown in __repr__ and used as DataFrame column order.
    _repr_fields: ClassVar[tuple[str, ...]]
    # The scalar twin of this class (identity for scalar classes, points to scalar from Batch).
    _scalar_cls: ClassVar["type[PayloadBase]"]
    # The batch twin of this class (identity until the Batch sibling is generated).
    _batch_cls: ClassVar["type[PayloadBase]"]
    # Cached map of attribute name → _BitFlag/_GroupMask descriptor, built once at class definition.
    _bitfields: ClassVar[dict[str, Any]]
    # Cached map of attribute name → default value for fields that declare one.
    _defaults: ClassVar[dict[str, Any]]
    # Auto-generated sibling class whose descriptors return NDArray views instead of scalars.
    Batch: ClassVar["type[PayloadBase]"]
    # Base element dtype (from the ``StructPayload[...]`` type arg); governs offset
    # arithmetic and the integer width used for masked reads. Defaults to uint8.
    _elem_dtype: ClassVar[np.dtype] = _DEFAULT_ELEMENT
    # Attribute name of the lone full-span member, if any: ``parse`` unwraps to it.
    _single_member: ClassVar[str | None] = None
    # The underlying numpy array holding one (0-D) or many (1-D) payload records.
    _arr: NDArray[NpStructT]

    def __init__(self, *args: object, **kwargs: object) -> None:
        cls = type(self)
        names = self.dtype.names
        if names is None:
            raise TypeError(f"{type(self).__name__}.dtype has no named fields")

        # TODO this is just to allow; PayloadU16(foo) syntax. Not sure if it is worth it?
        if args and kwargs:
            raise TypeError(
                f"{cls.__name__}() does not accept positional and keyword args together"
            )
        if args:
            if len(args) != 1 or len(names) != 1:
                raise TypeError(f"{cls.__name__}() takes exactly one positional argument")
            kwargs = {names[0]: args[0]}

        defaults = cls._defaults
        if defaults:
            merged = {k: v for k, v in defaults.items() if k not in kwargs}
            if merged:
                merged.update(kwargs)
                kwargs = merged

        arr = np.zeros((), dtype=self.dtype)

        # Route each kwarg by its descriptor kind, not by whether its name happens
        # to match a numpy slot — masked descriptors may share a slot whose name
        # collides with the first masked field's attribute name.
        for attr_name, value in kwargs.items():
            desc = cls._mro_descriptor(attr_name)
            if isinstance(desc, _FIELD_TYPES):
                desc._converter.encode_into(arr[desc._name], value)
            elif isinstance(desc, _BITFIELD_TYPES):
                slot = desc._slot
                mask_in_dtype = np.array(desc._mask, dtype=desc._dtype)
                if isinstance(desc, _BIT_FLAG_TYPES):
                    if value:
                        arr[slot] |= mask_in_dtype
                else:
                    int_val = desc._encode_value(value)
                    shifted = np.array((int_val << desc._shift) & desc._mask, dtype=desc._dtype)
                    arr[slot] = (arr[slot] & ~mask_in_dtype) | shifted
            elif attr_name in names:
                arr[attr_name] = value  # raw slot with no descriptor
            else:
                raise TypeError(f"{cls.__name__}() got unexpected kwarg: {attr_name!r}")

        self._arr = arr

    @classmethod
    def _mro_descriptor(cls, name: str) -> object | None:
        for klass in cls.__mro__:
            if name in klass.__dict__:
                return klass.__dict__[name]
        return None

    @classmethod
    def _collect_bitfields(
        cls,
    ) -> "dict[str, BitFlag | GroupMask | _BitFlagBatch | _GroupMaskBatch]":
        out: dict[str, Any] = {}
        for klass in reversed(cls.__mro__):
            for attr, val in klass.__dict__.items():
                if isinstance(val, _BITFIELD_TYPES):
                    out[attr] = val
        return out

    @classmethod
    def _collect_defaults(cls) -> "dict[str, Any]":
        out: dict[str, Any] = {}
        for klass in reversed(cls.__mro__):
            for attr, val in klass.__dict__.items():
                if isinstance(val, (Field, BitFlag, GroupMask)) and val._default is not _MISSING:
                    out[attr] = val._default
        return out

    def __init_subclass__(
        cls,
        *,
        _batch_of: "type[PayloadBase] | None" = None,
        length: int | None = None,
        **kwargs: object,
    ) -> None:
        super().__init_subclass__(**kwargs)

        if _batch_of is not None:
            # Auto-generated Batch sibling: borrow dtype/_repr_fields from its
            # scalar twin and wire the scalar↔batch pointers.
            cls.dtype = _batch_of.dtype
            cls._repr_fields = _batch_of._repr_fields
            cls._elem_dtype = _batch_of._elem_dtype
            cls._single_member = _batch_of._single_member
            cls._scalar_cls = _batch_of
            cls._batch_cls = cls
            _batch_of._batch_cls = cls
            return

        cls._elem_dtype = _resolve_element_dtype(cls)
        cls._single_member = None

        for name, val in cls.__dict__.items():
            if isinstance(val, _DECLARATION_TYPES) and name in _RESERVED_FIELD_NAMES:
                raise TypeError(f"{cls.__name__}: field name {name!r} is reserved by PayloadBase")

        own_declarations = [
            (name, val)
            for name, val in cls.__dict__.items()
            if isinstance(val, _SCALAR_DECLARATION_TYPES)
        ]

        if own_declarations:
            cls.dtype = _build_struct_dtype(cls, own_declarations, length)
            cls._single_member = _resolve_single_member(cls, own_declarations)

        if "_repr_fields" not in cls.__dict__:
            bitfield_names = tuple(
                name for name, val in vars(cls).items() if isinstance(val, (BitFlag, GroupMask))
            )
            if bitfield_names:
                cls._repr_fields = bitfield_names
            else:
                names = cls.dtype.names if hasattr(cls, "dtype") else None
                if names is not None and names != ("value",):
                    cls._repr_fields = names
                else:
                    cls._repr_fields = ("value",)

        cls._scalar_cls = cls
        cls._batch_cls = cls  # rebound below once Batch is generated

        if hasattr(cls, "dtype"):
            batch_attrs: dict[str, Any] = {"__init__": _batch_init_disabled}
            for name, val in cls.__dict__.items():
                if isinstance(val, _SCALAR_DECLARATION_TYPES):
                    batch_attrs[name] = val._to_batch()
            cls.Batch = type(
                f"{cls.__name__}Batch",
                (cls,),
                batch_attrs,
                _batch_of=cls,
            )

        cls._bitfields = cls._collect_bitfields()
        cls._defaults = cls._collect_defaults()

    @classmethod
    def from_array(cls, arr: "np.ndarray") -> Self:
        target = cls._scalar_cls if arr.ndim == 0 else cls._batch_cls
        obj = target.__new__(target)
        obj._arr = arr
        return obj  # type: ignore[return-value]

    @classmethod
    def from_buffer(cls, buf: bytes | bytearray | memoryview) -> Self:
        arr = np.frombuffer(buf, dtype=cls.dtype)
        return cls.from_array(arr[0] if len(arr) == 1 else arr)

    @property
    def raw_payload(self) -> NDArray[NpStructT]:
        return self._arr

    def to_dataframe(self, *, decode_enums: bool = True) -> pd.DataFrame:
        arr = np.atleast_1d(self._arr)
        cls = type(self)
        repr_fields = self._repr_fields

        has_bitfield = any(isinstance(cls._mro_descriptor(f), _BITFIELD_TYPES) for f in repr_fields)
        if has_bitfield:
            cols: dict[str, object] = {}
            for f in repr_fields:
                desc = cls._mro_descriptor(f)
                if isinstance(desc, _GROUP_MASK_TYPES):
                    slot_col = arr[desc._slot]
                    raw = (slot_col & desc._mask) >> desc._shift
                    if desc._enum is not None and decode_enums:
                        codes = desc._code_lookup[raw]
                        cols[f] = pd.Categorical.from_codes(codes, categories=desc._categories)
                    elif desc._enum is None and desc._converter is not None:
                        cols[f] = desc._converter.decode_batch(raw.astype(desc._converter.dtype))
                    else:
                        cols[f] = raw
                elif isinstance(desc, _BIT_FLAG_TYPES):
                    slot_col = arr[desc._slot]
                    cols[f] = (slot_col & desc._mask) != 0
                else:
                    cols[f] = np.atleast_1d(getattr(self, f))
            return pd.DataFrame(cols)

        cols = {}
        names = self.dtype.names
        single_value_slot = names == ("value",)
        for name in names:
            desc = cls._mro_descriptor(name)
            uses_converter = isinstance(desc, _FIELD_TYPES) and not isinstance(
                desc._converter, _IdentityConverter
            )
            if uses_converter:
                cols[name] = np.atleast_1d(getattr(self, name))
                continue

            field_dtype, _ = self.dtype.fields[name]
            sub = arr[name]
            if field_dtype.subdtype is None:
                cols[name] = sub
            else:
                _, subshape = field_dtype.subdtype
                count = int(np.prod(subshape))
                flat = sub.reshape(len(arr), count)
                for i in range(count):
                    col = str(i) if single_value_slot else f"{name}_{i}"
                    cols[col] = flat[:, i]
        return pd.DataFrame(cols)

    def __len__(self) -> int:
        return 1 if self._arr.ndim == 0 else len(self._arr)

    def _repr_kwargs(self) -> str:
        return ", ".join(f"{f}={getattr(self, f)!r}" for f in self._repr_fields)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._repr_kwargs()})"

    def __str__(self) -> str:
        return repr(self)

    @classmethod
    def unwrap(cls, arr: "np.ndarray") -> Any:
        """Dispatch hook used by ``RegisterBase.parse``.

        Struct payloads return a typed wrapper so descriptors like
        ``payload.Channel0`` work. Anonymous payloads override this to
        return the raw numpy scalar/ndarray directly.

        This allows us to not have to use hacky descriptors for single-field
        struct payloads (e.g. a struct with one uint16 field can just be a
        PayloadU16 subclass) while still supporting the full descriptor
        machinery for multi-field struct payloads.

        A struct payload with exactly one full-span member (register-level
        ``interfaceType``) unwraps directly to that member's value.
        """
        obj = cls.from_array(arr)
        if cls._single_member is not None and arr.ndim == 0:
            return getattr(obj, cls._single_member)
        return obj


# ---------------------------------------------------------------------------
# StructPayload — base for named-field (struct) register payloads
# ---------------------------------------------------------------------------


@dataclass_transform(
    kw_only_default=True,
    field_specifiers=(Field, BitFlag, GroupMask),
)
class StructPayload(PayloadBase[NpStructT]):
    """Base class for struct register payloads with typed field descriptors.

    Subclasses declare fields using ``Field``, ``BitFlag``, or ``GroupMask``
    descriptors.  Type checkers synthesize a keyword-only ``__init__`` from
    those declarations, so constructor calls are fully type-checked and have
    IDE autocompletion.

    The type argument (``StructPayload[np.uint8]``) is the base element type; it
    sets the unit for ``offset=`` and the integer width of masked reads. The
    optional ``length=`` class kwarg fixes the payload size in base elements
    (the register ``length``); when omitted it defaults to the max member extent.

    Example::

        class MyPayload(StructPayload[np.uint8]):
            channel: np.uint16 = Field(UInt16Converter(), offset=0)
            enabled: bool = BitFlag(mask=0x01, offset=2)
    """


# ---------------------------------------------------------------------------
# AnonymousPayload — single unnamed slot, no user-facing descriptors
# ---------------------------------------------------------------------------


class AnonymousPayload(PayloadBase[NpStructT]):
    """Payload backed by a single unnamed numpy dtype (scalar or sub-array).

    Subclasses declare the dtype via class kwargs, not descriptors:

        class PayloadU16(AnonymousPayload, scalar_dtype="<u2"): ...

    Used for scalar/array Harp registers whose payload has no internal
    structure. ``RegisterBase.parse`` unwraps these to a raw numpy scalar
    (for 0-D) or ndarray (for sub-array / batch) — there is no
    ``.value`` accessor and the slot name ``value`` is free for use by
    struct payloads.
    """

    def __init_subclass__(
        cls,
        *,
        scalar_dtype: "np.dtype | str | type | None" = None,
        **kwargs: object,
    ) -> None:
        if scalar_dtype is not None:
            cls.dtype = np.dtype(scalar_dtype)
            cls._repr_fields = ()
        super().__init_subclass__(**kwargs)

    def __init__(self, value: object = _MISSING_INIT, /, **kwargs: object) -> None:  # type: ignore[override]
        if value is _MISSING_INIT:
            if "value" in kwargs:
                value = kwargs.pop("value")
            else:
                raise TypeError(f"{type(self).__name__}() requires a value")
        if kwargs:
            raise TypeError(f"{type(self).__name__}() got unexpected kwargs: {sorted(kwargs)}")
        self._arr = np.asarray(value, dtype=self.dtype)

    @classmethod
    def unwrap(cls, arr: "np.ndarray") -> Any:
        # 0-D → numpy scalar via item-like access (preserves dtype).
        # 1-D / sub-array → return the ndarray as-is.
        return arr if arr.ndim > 0 else arr[()]

    def _repr_kwargs(self) -> str:
        return repr(self._arr.tolist() if self._arr.ndim > 0 else self._arr[()])

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._repr_kwargs()})"

    def to_dataframe(self, *, decode_enums: bool = True) -> pd.DataFrame:
        arr = np.atleast_1d(self._arr)
        # Sub-array dtype (array register): shape is already (N, length).
        if arr.ndim > 1:
            return pd.DataFrame({str(i): arr[:, i] for i in range(arr.shape[1])})
        return pd.DataFrame({"value": arr})


@final
class PayloadU8(AnonymousPayload[np.uint8], scalar_dtype=np.dtype("u1")):
    pass


@final
class PayloadU16(AnonymousPayload[np.uint16], scalar_dtype=np.dtype("<u2")):
    pass


@final
class PayloadU32(AnonymousPayload[np.uint32], scalar_dtype=np.dtype("<u4")):
    pass


@final
class PayloadU64(AnonymousPayload[np.uint64], scalar_dtype=np.dtype("<u8")):
    pass


@final
class PayloadS8(AnonymousPayload[np.int8], scalar_dtype=np.dtype("i1")):
    pass


@final
class PayloadS16(AnonymousPayload[np.int16], scalar_dtype=np.dtype("<i2")):
    pass


@final
class PayloadS32(AnonymousPayload[np.int32], scalar_dtype=np.dtype("<i4")):
    pass


@final
class PayloadS64(AnonymousPayload[np.int64], scalar_dtype=np.dtype("<i8")):
    pass


@final
class PayloadFloat(AnonymousPayload[np.float32], scalar_dtype=np.dtype("<f4")):
    pass


# Array payload base classes — concrete sub-dtype is set by ``RegisterBase``
# array metaclass when a length is supplied (e.g. ``RegisterU16Array(0x28, length=3)``).
@final
class PayloadU8Array(AnonymousPayload[np.uint8], scalar_dtype=np.dtype("u1")):
    pass


@final
class PayloadU16Array(AnonymousPayload[np.uint16], scalar_dtype=np.dtype("<u2")):
    pass


@final
class PayloadU32Array(AnonymousPayload[np.uint32], scalar_dtype=np.dtype("<u4")):
    pass


@final
class PayloadU64Array(AnonymousPayload[np.uint64], scalar_dtype=np.dtype("<u8")):
    pass


@final
class PayloadS8Array(AnonymousPayload[np.int8], scalar_dtype=np.dtype("i1")):
    pass


@final
class PayloadS16Array(AnonymousPayload[np.int16], scalar_dtype=np.dtype("<i2")):
    pass


@final
class PayloadS32Array(AnonymousPayload[np.int32], scalar_dtype=np.dtype("<i4")):
    pass


@final
class PayloadS64Array(AnonymousPayload[np.int64], scalar_dtype=np.dtype("<i8")):
    pass


@final
class PayloadFloatArray(AnonymousPayload[np.float32], scalar_dtype=np.dtype("<f4")):
    pass
