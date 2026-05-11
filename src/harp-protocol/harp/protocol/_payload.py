from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, TypeVar, final

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from typing_extensions import Self

NpStructT = TypeVar("NpStructT", bound=np.generic)


class _Converter(ABC):
    dtype: np.dtype
    python_type: type

    @abstractmethod
    def decode_scalar(self, view: Any) -> Any: ...

    @abstractmethod
    def decode_batch(self, view: Any) -> Any: ...

    @abstractmethod
    def encode_into(self, view: Any, value: Any) -> None: ...


class _IdentityConverter(_Converter):
    def __init__(self, dtype: "np.dtype | str | type") -> None:
        self.dtype = np.dtype(dtype)
        self.python_type = self.dtype.type

    def decode_scalar(self, view: Any) -> Any:
        return view

    def decode_batch(self, view: Any) -> Any:
        return view

    def encode_into(self, view: Any, value: Any) -> None:
        view[...] = value


class _StringConverter(_Converter):
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


class _Field:
    def __init__(self, converter: _Converter, *, name: str | None = None) -> None:
        self._converter = converter
        self._name = name

    def __set_name__(self, owner: object, name: str) -> None:
        if self._name is None:
            self._name = name

    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> Any:
        if obj is None:
            return self
        view = obj._arr[self._name]
        if obj._arr.ndim == 0:
            return self._converter.decode_scalar(view)
        return self._converter.decode_batch(view)


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

    def __get__(
        self, obj: "PayloadBase | None", owner: object = None
    ) -> "bool | NDArray[np.bool_]":
        if obj is None:
            return self  # type: ignore[return-value]
        view = obj._arr[self._slot]
        result = (view & self._mask) != 0
        if obj._arr.ndim == 0:
            return bool(result)
        return result


def _build_enum_lookup(enum: type) -> "tuple[list[str], np.ndarray]":
    members = list(enum)
    categories = [m.name for m in members]
    max_val = max(int(m) for m in members)
    code_dtype = np.int8 if len(members) < 128 else np.int32
    code_lookup = np.full(max_val + 1, -1, dtype=code_dtype)
    for code, m in enumerate(members):
        code_lookup[int(m)] = code
    return categories, code_lookup


class _GroupMask:
    def __init__(
        self,
        mask: int,
        shift: int,
        enum: type,
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

    def __get__(self, obj: "PayloadBase | None", owner: object = None):
        if obj is None:
            return self
        view = obj._arr[self._slot]
        raw = (view & self._mask) >> self._shift
        if obj._arr.ndim == 0:
            return self._enum(int(raw))
        return raw


_BITFIELD_TYPES = (_BitFlag, _GroupMask)
_DECLARATION_TYPES = (_Field, _BitFlag, _GroupMask)

# value/raw_payload deliberately omitted: overriding them is the intended
# pattern for single-slot converter-driven payloads.
_RESERVED_FIELD_NAMES = frozenset({"_arr", "_dtype", "_repr_fields"})


class PayloadBase(Generic[NpStructT]):
    """Base class for typed Harp register payloads."""

    _dtype: ClassVar[np.dtype]
    _repr_fields: ClassVar[tuple[str, ...]]
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
            if isinstance(desc, _Field):
                desc._converter.encode_into(arr[name], slot_kwargs[name])
            else:
                arr[name] = slot_kwargs[name]

        for attr_name, value in descriptor_kwargs.items():
            desc = bitfields[attr_name]
            slot = desc._slot
            mask_in_dtype = np.array(desc._mask, dtype=desc._dtype)
            if isinstance(desc, _BitFlag):
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
    def _collect_bitfields(cls) -> dict[str, "_BitFlag | _GroupMask"]:
        out: dict[str, _BitFlag | _GroupMask] = {}
        for klass in reversed(cls.__mro__):
            for attr, val in klass.__dict__.items():
                if isinstance(val, _BITFIELD_TYPES):
                    out[attr] = val
        return out

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        for name, val in cls.__dict__.items():
            if isinstance(val, _DECLARATION_TYPES) and name in _RESERVED_FIELD_NAMES:
                raise TypeError(f"{cls.__name__}: field name {name!r} is reserved by PayloadBase")

        own_declarations = [
            (name, val) for name, val in cls.__dict__.items() if isinstance(val, _DECLARATION_TYPES)
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
                name for name, val in vars(cls).items() if isinstance(val, _BITFIELD_TYPES)
            )
            if bitfield_names:
                cls._repr_fields = bitfield_names
            else:
                names = cls._dtype.names if hasattr(cls, "_dtype") else None
                if names is not None and names != ("value",):
                    cls._repr_fields = names
                else:
                    cls._repr_fields = ("value",)

    @classmethod
    def from_array(cls, arr: "np.ndarray") -> Self:
        obj = cls.__new__(cls)
        obj._arr = arr
        return obj

    @classmethod
    def from_buffer(cls, buf: bytes | bytearray | memoryview) -> Self:
        arr = np.frombuffer(buf, dtype=cls._dtype)
        obj = cls.__new__(cls)
        obj._arr = arr
        return obj

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
                if isinstance(desc, _GroupMask):
                    slot_col = arr[desc._slot]
                    raw = (slot_col & desc._mask) >> desc._shift
                    if decode_enums:
                        codes = desc._code_lookup[raw]
                        cols[f] = pd.Categorical.from_codes(codes, categories=desc._categories)
                    else:
                        cols[f] = raw
                elif isinstance(desc, _BitFlag):
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
            uses_converter = isinstance(desc, _Field) and not isinstance(
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
