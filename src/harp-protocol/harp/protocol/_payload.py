import enum
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar, final, overload

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from typing_extensions import Self

NpStructT = TypeVar("NpStructT", bound=np.generic)
T = TypeVar("T")
E = TypeVar("E", bound=enum.IntEnum)
NpScalarT = TypeVar("NpScalarT", bound=np.generic)


# ---------------------------------------------------------------------------
# Converters
# ---------------------------------------------------------------------------


class _Converter(ABC, Generic[T]):
    dtype: np.dtype
    python_type: type

    @abstractmethod
    def decode_scalar(self, view: Any) -> T: ...

    @abstractmethod
    def decode_batch(self, view: Any) -> Any: ...

    @abstractmethod
    def encode_into(self, view: Any, value: Any) -> None: ...


class _IdentityConverter(_Converter[NpScalarT]):
    def __init__(self, dtype: "np.dtype[NpScalarT] | str | type[NpScalarT]") -> None:
        self.dtype = np.dtype(dtype)
        self.python_type = self.dtype.type

    def decode_scalar(self, view: Any) -> NpScalarT:
        return view

    def decode_batch(self, view: Any) -> "NDArray[NpScalarT]":
        return view

    def encode_into(self, view: Any, value: NpScalarT) -> None:
        view[...] = value


class _StringConverter(_Converter[str]):
    python_type = str

    def __init__(self, length: int, encoding: str = "ascii") -> None:
        self._length = length
        self._encoding = encoding
        self.dtype = np.dtype((np.uint8, (length,)))

    def decode_scalar(self, view: Any) -> str:
        return bytes(view).rstrip(b"\x00").decode(self._encoding)

    def decode_batch(self, view: Any) -> Any:
        return np.array(
            [bytes(row).rstrip(b"\x00").decode(self._encoding) for row in view],
            dtype=object,
        )

    def encode_into(self, view: Any, value: str) -> None:
        encoded = value.encode(self._encoding)[: self._length]
        padded = encoded.ljust(self._length, b"\x00")
        view[...] = np.frombuffer(padded, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Descriptors — scalar variants (return Python / 0-D types)
# ---------------------------------------------------------------------------
# A PayloadBase subclass declares fields with the scalar descriptors below.
# `__init_subclass__` auto-derives a Batch sibling whose descriptors are
# swapped to the matching ``*Batch`` counterpart via ``_to_batch()`` and
# return ``NDArray`` views instead.


class _Field(Generic[T]):
    def __init__(self, converter: _Converter[T], *, name: str | None = None) -> None:
        self._converter = converter
        self._name = name

    def __set_name__(self, owner: object, name: str) -> None:
        if self._name is None:
            self._name = name

    @overload
    def __get__(self, obj: None, owner: object = None) -> "_Field[T]": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> T: ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        return self._converter.decode_scalar(obj._arr[self._name])

    def _to_batch(self) -> "_FieldBatch[T]":
        return _FieldBatch(self._converter, name=self._name)


class _BitFlag:
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
    def __get__(self, obj: None, owner: object = None) -> "_BitFlag": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> bool: ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        return bool(obj._arr[self._slot] & self._mask)

    def _to_batch(self) -> "_BitFlagBatch":
        return _BitFlagBatch(self._mask, slot=self._slot, dtype=self._dtype)


def _build_enum_lookup(enum_cls: type) -> "tuple[list[str], np.ndarray]":
    members = list(enum_cls)
    categories = [m.name for m in members]
    max_val = max(int(m) for m in members)
    code_dtype = np.int8 if len(members) < 128 else np.int32
    code_lookup = np.full(max_val + 1, -1, dtype=code_dtype)
    for code, m in enumerate(members):
        code_lookup[int(m)] = code
    return categories, code_lookup


class _GroupMask(Generic[E]):
    def __init__(
        self,
        mask: int,
        shift: int,
        enum: type[E],
        *,
        slot: str = "value",
        dtype: "np.dtype | str | type" = np.uint8,
    ) -> None:
        self._mask = mask
        self._shift = shift
        self._enum = enum
        self._slot = slot
        self._dtype = np.dtype(dtype)
        self._categories, self._code_lookup = _build_enum_lookup(enum)

    @overload
    def __get__(self, obj: None, owner: object = None) -> "_GroupMask[E]": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> E: ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        raw = (obj._arr[self._slot] & self._mask) >> self._shift
        return self._enum(int(raw))

    def _to_batch(self) -> "_GroupMaskBatch[E]":
        return _GroupMaskBatch(
            self._mask,
            self._shift,
            self._enum,
            slot=self._slot,
            dtype=self._dtype,
        )


# ---------------------------------------------------------------------------
# Descriptors — batch variants (return ndarray views)
# ---------------------------------------------------------------------------


class _FieldBatch(Generic[T]):
    def __init__(self, converter: _Converter[T], *, name: str | None = None) -> None:
        self._converter = converter
        self._name = name

    def __set_name__(self, owner: object, name: str) -> None:
        if self._name is None:
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
    def __init__(
        self,
        mask: int,
        shift: int,
        enum: type[E],
        *,
        slot: str = "value",
        dtype: "np.dtype | str | type" = np.uint8,
    ) -> None:
        self._mask = mask
        self._shift = shift
        self._enum = enum
        self._slot = slot
        self._dtype = np.dtype(dtype)
        self._categories, self._code_lookup = _build_enum_lookup(enum)

    @overload
    def __get__(self, obj: None, owner: object = None) -> "_GroupMaskBatch[E]": ...
    @overload
    def __get__(self, obj: "PayloadBase", owner: object = None) -> "NDArray[np.signedinteger]": ...
    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        return (obj._arr[self._slot] & self._mask) >> self._shift


_PT = TypeVar("_PT", bound="PayloadBase[Any]")


class Batch(Generic[_PT]):
    """Phantom type for batched payloads.

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


# Tuples used by isinstance() checks throughout the module.
_SCALAR_DECLARATION_TYPES = (_Field, _BitFlag, _GroupMask)
_BATCH_DECLARATION_TYPES = (_FieldBatch, _BitFlagBatch, _GroupMaskBatch)
_DECLARATION_TYPES = _SCALAR_DECLARATION_TYPES + _BATCH_DECLARATION_TYPES
_BITFIELD_TYPES = (_BitFlag, _GroupMask, _BitFlagBatch, _GroupMaskBatch)
_FIELD_TYPES = (_Field, _FieldBatch)
_GROUP_MASK_TYPES = (_GroupMask, _GroupMaskBatch)
_BIT_FLAG_TYPES = (_BitFlag, _BitFlagBatch)

# value/raw_payload deliberately omitted: overriding them is the intended
# pattern for single-slot converter-driven payloads.
_RESERVED_FIELD_NAMES = frozenset({"_arr", "_dtype", "_repr_fields", "Batch"})


def _batch_init_disabled(self: "PayloadBase", *args: object, **kwargs: object) -> None:
    raise TypeError(
        f"{type(self).__name__} is a Batch payload; construct it via "
        f"from_array()/from_buffer() (or use its scalar twin "
        f"{type(self)._scalar_cls.__name__!s})."
    )


class PayloadBase(Generic[NpStructT]):
    """Base class for typed Harp register payloads.

    A subclass declares fields via the scalar descriptors above.
    ``__init_subclass__`` auto-derives a ``Batch`` sibling subclass with the
    same dtype but each descriptor swapped to a Batch variant returning an
    ``NDArray`` view. ``from_array`` routes by ``ndim`` so callers never need
    to mention the Batch class explicitly: 0-D records stay scalar, 1-D
    buffers become Batch.
    """

    _dtype: ClassVar[np.dtype]
    _repr_fields: ClassVar[tuple[str, ...]]
    _scalar_cls: ClassVar["type[PayloadBase]"]
    _batch_cls: ClassVar["type[PayloadBase]"]
    Batch: ClassVar["type[PayloadBase]"]
    _arr: NDArray[NpStructT]

    def __init__(self, *args: object, **kwargs: object) -> None:
        cls = type(self)
        names = self._dtype.names
        assert names is not None

        if args and kwargs:
            raise TypeError(
                f"{cls.__name__}() does not accept positional and keyword args together"
            )
        if args:
            if len(args) != 1 or len(names) != 1:
                raise TypeError(f"{cls.__name__}() takes exactly one positional argument")
            kwargs = {names[0]: args[0]}

        slot_kwargs = {k: v for k, v in kwargs.items() if k in names}
        descriptor_kwargs = {k: v for k, v in kwargs.items() if k not in names}

        bitfields = cls._collect_bitfields()
        unknown = set(descriptor_kwargs) - set(bitfields)
        if unknown:
            raise TypeError(f"{cls.__name__}() got unexpected kwargs: {sorted(unknown)}")

        arr = np.zeros((), dtype=self._dtype)

        for name in names:
            if name not in slot_kwargs:
                continue
            desc = cls._mro_descriptor(name)
            if isinstance(desc, _FIELD_TYPES):
                desc._converter.encode_into(arr[name], slot_kwargs[name])
            else:
                arr[name] = slot_kwargs[name]

        for attr_name, value in descriptor_kwargs.items():
            desc = bitfields[attr_name]
            slot = desc._slot
            mask_in_dtype = np.array(desc._mask, dtype=desc._dtype)
            if isinstance(desc, _BIT_FLAG_TYPES):
                if value:
                    arr[slot] |= mask_in_dtype
            else:
                shifted = np.array((int(value) << desc._shift) & desc._mask, dtype=desc._dtype)
                arr[slot] = (arr[slot] & ~mask_in_dtype) | shifted

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
    ) -> "dict[str, _BitFlag | _GroupMask | _BitFlagBatch | _GroupMaskBatch]":
        out: dict[str, Any] = {}
        for klass in reversed(cls.__mro__):
            for attr, val in klass.__dict__.items():
                if isinstance(val, _BITFIELD_TYPES):
                    out[attr] = val
        return out

    def __init_subclass__(
        cls,
        *,
        _batch_of: "type[PayloadBase] | None" = None,
        **kwargs: object,
    ) -> None:
        super().__init_subclass__(**kwargs)

        if _batch_of is not None:
            # Auto-generated Batch sibling: borrow dtype/_repr_fields from its
            # scalar twin and wire the scalar↔batch pointers.
            cls._dtype = _batch_of._dtype
            cls._repr_fields = _batch_of._repr_fields
            cls._scalar_cls = _batch_of
            cls._batch_cls = cls
            _batch_of._batch_cls = cls
            return

        for name, val in cls.__dict__.items():
            if isinstance(val, _DECLARATION_TYPES) and name in _RESERVED_FIELD_NAMES:
                raise TypeError(f"{cls.__name__}: field name {name!r} is reserved by PayloadBase")

        own_declarations = [
            (name, val)
            for name, val in cls.__dict__.items()
            if isinstance(val, _SCALAR_DECLARATION_TYPES)
        ]

        if own_declarations:
            slots: dict[str, np.dtype] = {}
            for attr_name, val in own_declarations:
                if isinstance(val, _Field):
                    if val._name is None:
                        val._name = attr_name
                    slot, dtype = val._name, val._converter.dtype
                else:
                    slot, dtype = val._slot, val._dtype
                if slot in slots:
                    if slots[slot] != dtype:
                        raise TypeError(
                            f"{cls.__name__}: slot {slot!r} declared with conflicting "
                            f"dtypes {slots[slot]} and {dtype}"
                        )
                else:
                    slots[slot] = dtype
            cls._dtype = np.dtype(list(slots.items()))

        if "_repr_fields" not in cls.__dict__:
            bitfield_names = tuple(
                name for name, val in vars(cls).items() if isinstance(val, (_BitFlag, _GroupMask))
            )
            if bitfield_names:
                cls._repr_fields = bitfield_names
            else:
                names = cls._dtype.names if hasattr(cls, "_dtype") else None
                if names is not None and names != ("value",):
                    cls._repr_fields = names
                else:
                    cls._repr_fields = ("value",)

        cls._scalar_cls = cls
        cls._batch_cls = cls  # rebound below once Batch is generated

        if hasattr(cls, "_dtype"):
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

    @classmethod
    def from_array(cls, arr: "np.ndarray") -> Self:
        target = cls._scalar_cls if arr.ndim == 0 else cls._batch_cls
        obj = target.__new__(target)
        obj._arr = arr
        return obj  # type: ignore[return-value]

    @classmethod
    def from_buffer(cls, buf: bytes | bytearray | memoryview) -> Self:
        arr = np.frombuffer(buf, dtype=cls._dtype)
        return cls.from_array(arr)

    @property
    def value(self) -> "NDArray[NpStructT]":
        arr = self._arr
        if arr.dtype.names == ("value",):
            return arr["value"]
        return arr

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
                    if decode_enums:
                        codes = desc._code_lookup[raw]
                        cols[f] = pd.Categorical.from_codes(codes, categories=desc._categories)
                    else:
                        cols[f] = raw
                elif isinstance(desc, _BIT_FLAG_TYPES):
                    slot_col = arr[desc._slot]
                    cols[f] = (slot_col & desc._mask) != 0
                else:
                    cols[f] = np.atleast_1d(getattr(self, f))
            return pd.DataFrame(cols)

        cols = {}
        names = self._dtype.names
        single_value_slot = names == ("value",)
        for name in names:
            desc = cls._mro_descriptor(name)
            uses_converter = isinstance(desc, _FIELD_TYPES) and not isinstance(
                desc._converter, _IdentityConverter
            )
            if uses_converter:
                cols[name] = np.atleast_1d(getattr(self, name))
                continue

            field_dtype, _ = self._dtype.fields[name]
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


class PayloadU8(PayloadBase[np.uint8]):
    value = _Field(_IdentityConverter(np.dtype("u1")))


class PayloadU16(PayloadBase[np.uint16]):
    value = _Field(_IdentityConverter(np.dtype("<u2")))


class PayloadU32(PayloadBase[np.uint32]):
    value = _Field(_IdentityConverter(np.dtype("<u4")))


class PayloadU64(PayloadBase[np.uint64]):
    value = _Field(_IdentityConverter(np.dtype("<u8")))


class PayloadS8(PayloadBase[np.int8]):
    value = _Field(_IdentityConverter(np.dtype("i1")))


class PayloadS16(PayloadBase[np.int16]):
    value = _Field(_IdentityConverter(np.dtype("<i2")))


class PayloadS32(PayloadBase[np.int32]):
    value = _Field(_IdentityConverter(np.dtype("<i4")))


class PayloadS64(PayloadBase[np.int64]):
    value = _Field(_IdentityConverter(np.dtype("<i8")))


class PayloadFloat(PayloadBase[np.float32]):
    value = _Field(_IdentityConverter(np.dtype("<f4")))


@final
class PayloadU8Array(PayloadBase[NDArray[np.uint8]]):
    value = _Field(_IdentityConverter(np.dtype("u1")))


@final
class PayloadU16Array(PayloadBase[NDArray[np.uint16]]):
    value = _Field(_IdentityConverter(np.dtype("<u2")))


@final
class PayloadU32Array(PayloadBase[NDArray[np.uint32]]):
    value = _Field(_IdentityConverter(np.dtype("<u4")))


@final
class PayloadU64Array(PayloadBase[NDArray[np.uint64]]):
    value = _Field(_IdentityConverter(np.dtype("<u8")))


@final
class PayloadS8Array(PayloadBase[NDArray[np.int8]]):
    value = _Field(_IdentityConverter(np.dtype("i1")))


@final
class PayloadS16Array(PayloadBase[NDArray[np.int16]]):
    value = _Field(_IdentityConverter(np.dtype("<i2")))


@final
class PayloadS32Array(PayloadBase[NDArray[np.int32]]):
    value = _Field(_IdentityConverter(np.dtype("<i4")))


@final
class PayloadS64Array(PayloadBase[NDArray[np.int64]]):
    value = _Field(_IdentityConverter(np.dtype("<i8")))


@final
class PayloadFloatArray(PayloadBase[NDArray[np.float32]]):
    value = _Field(_IdentityConverter(np.dtype("<f4")))
