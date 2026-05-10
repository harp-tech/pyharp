import inspect
from typing import ClassVar, Generic, TypeVar, final

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from typing_extensions import Self

NpStructT = TypeVar("NpStructT", bound=np.generic)


# ---------------------------------------------------------------------------
# Descriptors
# ---------------------------------------------------------------------------
# Each descriptor comes in a Scalar / Batch pair. The Scalar variant is what
# codegen and hand-written payloads declare; ``PayloadBase.__init_subclass__``
# auto-derives a ``.Batch`` sibling class with the descriptors swapped to
# their Batch counterparts. Same compute, distinct return-type annotations.
#
#   parse(msg)        -> payload_class       (uses Scalar descriptors → Python/0-D)
#   read_frames(buf)  -> payload_class.Batch (uses Batch descriptors  → ndarray)


class _BitFlag:
    """Single-bit boolean field. Returns ``bool`` from a 0-D record."""

    def __init__(self, mask: int) -> None:
        self._mask = mask

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> bool:
        if obj is None:
            return self  # type: ignore[return-value]
        return bool((obj._arr["value"] & self._mask) != 0)


class _BitFlagBatch:
    """Batch counterpart of ``_BitFlag``. Returns ``NDArray[bool_]``."""

    def __init__(self, mask: int) -> None:
        self._mask = mask

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> "NDArray[np.bool_]":
        if obj is None:
            return self  # type: ignore[return-value]
        return (obj._arr["value"] & self._mask) != 0


def _build_enum_lookup(enum: type) -> "tuple[list[str], np.ndarray]":
    """Pre-compute (categories, code_lookup) used by ``to_dataframe`` for a group mask."""
    members = list(enum)
    categories = [m.name for m in members]
    max_val = max(int(m) for m in members)
    code_dtype = np.int8 if len(members) < 128 else np.int32
    code_lookup = np.full(max_val + 1, -1, dtype=code_dtype)
    for code, m in enumerate(members):
        code_lookup[int(m)] = code
    return categories, code_lookup


class _GroupMask:
    """Multi-bit enum field. Returns the IntEnum member from a 0-D record."""

    def __init__(self, mask: int, shift: int, enum: type) -> None:
        self._mask = mask
        self._shift = shift
        self._enum = enum
        self._categories, self._code_lookup = _build_enum_lookup(enum)

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    def __get__(self, obj: "PayloadBase | None", owner: object = None):
        if obj is None:
            return self
        raw = (obj._arr["value"] & self._mask) >> self._shift
        return self._enum(int(raw))


class _GroupMaskBatch:
    """Batch counterpart of ``_GroupMask``. Returns the raw integer ``NDArray``."""

    def __init__(self, mask: int, shift: int, enum: type) -> None:
        self._mask = mask
        self._shift = shift
        self._enum = enum
        self._categories, self._code_lookup = _build_enum_lookup(enum)

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> np.ndarray:
        if obj is None:
            return self  # type: ignore[return-value]
        return (obj._arr["value"] & self._mask) >> self._shift


class _Field:
    """Struct field accessor. Returns the 0-D numpy scalar for that field."""

    def __init__(self, field_name: str) -> None:
        self._field = field_name

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    def __get__(self, obj: "PayloadBase | None", owner: object = None):
        if obj is None:
            return self
        return obj._arr[self._field]


class _FieldBatch:
    """Batch counterpart of ``_Field``. Returns the 1-D ``NDArray`` for that field."""

    def __init__(self, field_name: str) -> None:
        self._field = field_name

    def __set_name__(self, owner: object, name: str) -> None:
        self._name = name

    def __get__(self, obj: "PayloadBase | None", owner: object = None) -> np.ndarray:
        if obj is None:
            return self  # type: ignore[return-value]
        return obj._arr[self._field]


# Pairing table used by ``__init_subclass__`` to derive ``.Batch``.
def _swap_to_batch(val: object) -> object | None:
    if isinstance(val, _BitFlag):
        return _BitFlagBatch(val._mask)
    if isinstance(val, _GroupMask):
        return _GroupMaskBatch(val._mask, val._shift, val._enum)
    if isinstance(val, _Field):
        return _FieldBatch(val._field)
    return None


_SCALAR_BITFIELD_TYPES = (_BitFlag, _GroupMask)
_BATCH_BITFIELD_TYPES = (_BitFlagBatch, _GroupMaskBatch)
_GROUP_TYPES = (_GroupMask, _GroupMaskBatch)
_FLAG_TYPES = (_BitFlag, _BitFlagBatch)


# ---------------------------------------------------------------------------
# PayloadBase
# ---------------------------------------------------------------------------


class PayloadBase(Generic[NpStructT]):
    """Base class for typed Harp register payloads.

    Storage contract for ``_arr``:

    * ``ndim == 0`` — single record (produced by ``__init__`` and by
      ``RegisterBase.parse``). Descriptor reads return Python / 0-D scalars.
    * ``ndim == 1`` — batch of N records (produced by
      ``RegisterBase.read_frames``). Lives on the ``.Batch`` sibling class
      whose descriptors return ``ndarray``.

    ``_dtype`` is **always** a structured dtype. When a subclass declares a
    primitive or sub-array dtype, ``__init_subclass__`` auto-promotes it to a
    single-field structured dtype with the field name ``"value"``.

    For multi-field structured payloads (e.g. ``AnalogData``), per-field
    accessor descriptors are auto-generated from ``_dtype.names`` — codegen
    does not need to declare them.
    """

    _dtype: ClassVar[np.dtype]
    _repr_fields: ClassVar[tuple[str, ...]]
    Batch: ClassVar[type["PayloadBase"]]
    _arr: NDArray[NpStructT]

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Construct a single-record payload (``_arr`` is 0-D)."""
        names = self._dtype.names
        assert names is not None  # invariant: __init_subclass__ promotes everything
        if names == ("value",):
            if len(args) != 1 or kwargs:
                raise TypeError(f"{type(self).__name__}() takes exactly one positional argument")
            self._arr = np.array((args[0],), dtype=self._dtype)
        else:
            if args:
                raise TypeError(
                    f"{type(self).__name__}() requires keyword arguments, got positional args"
                )
            unknown = set(kwargs) - set(names)
            if unknown:
                raise TypeError(f"{type(self).__name__}() got unexpected kwargs: {sorted(unknown)}")
            values = tuple(kwargs[n] for n in names)
            self._arr = np.array(values, dtype=self._dtype)

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # 1. Promote _dtype if it was provided as a primitive.
        if "_dtype" in cls.__dict__:
            raw = cls.__dict__["_dtype"]
            if not isinstance(raw, np.dtype):
                raw = np.dtype(raw)
            if raw.names is None:
                raw = np.dtype([("value", raw)])
            cls._dtype = raw

        # 2. Skip auto-derived Batch siblings so we don't recurse / re-pair.
        if cls.__dict__.get("_is_batch_view", False):
            return

        # 3. Multi-field struct payloads: auto-generate _Field accessors for
        #    any name that the user hasn't already declared.
        has_bitfield = any(isinstance(val, _SCALAR_BITFIELD_TYPES) for val in vars(cls).values())
        names = cls._dtype.names
        if not has_bitfield and names is not None and names != ("value",):
            for name in names:
                if name not in vars(cls):
                    setattr(cls, name, _Field(name))

        # 4. Auto-derive _repr_fields if not explicitly set on this class.
        if "_repr_fields" not in cls.__dict__:
            bitfield_names = tuple(
                name for name, val in vars(cls).items() if isinstance(val, _SCALAR_BITFIELD_TYPES)
            )
            if bitfield_names:
                cls._repr_fields = bitfield_names
            elif names is not None and names != ("value",):
                cls._repr_fields = names
            else:
                cls._repr_fields = ("value",)

        # 5. Synthesise the .Batch sibling by swapping each declared
        #    descriptor for its batch counterpart. If nothing to swap, the
        #    class is its own Batch (e.g. plain scalar PayloadU8).
        batch_attrs: dict[str, object] = {"_is_batch_view": True}
        for name, val in vars(cls).items():
            swapped = _swap_to_batch(val)
            if swapped is not None:
                batch_attrs[name] = swapped

        if len(batch_attrs) > 1:
            cls.Batch = type(f"{cls.__name__}Batch", (cls,), batch_attrs)
        else:
            cls.Batch = cls

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_array(cls, arr: "np.ndarray") -> Self:
        """Wrap a pre-built numpy array of ``_dtype`` records.

        The shape of ``arr`` determines the storage mode: 0-D = single record
        (used by ``parse``), 1-D = batch (used by ``read_frames``). For batch
        construction in tests, call this on the ``.Batch`` sibling class.
        """
        obj = cls.__new__(cls)
        obj._arr = arr
        return obj

    @classmethod
    def from_buffer(cls, buf: bytes | bytearray | memoryview) -> Self:
        """Decode a packed byte buffer into a batch payload (``_arr.ndim == 1``).

        Always returns an instance of ``cls.Batch`` so descriptor reads
        produce ``ndarray`` columns regardless of the calling class. Use
        :py:meth:`RegisterBase.parse` for the single-record / scalar path.
        """
        arr = np.frombuffer(buf, dtype=cls._dtype)
        batch_cls = cls.Batch
        obj = batch_cls.__new__(batch_cls)
        obj._arr = arr
        return obj  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Value accessors
    # ------------------------------------------------------------------

    @property
    def value(self) -> "NDArray[NpStructT]":
        """Return the underlying value(s).

        For single-field ``("value",)`` payloads:
        * 0-D _arr → 0-D numpy scalar (``np.uint16(1216)``) for primitive
          registers, or 1-D sub-array for fixed-length array registers.
        * 1-D _arr → 1-D ndarray (or 2-D for array registers).

        For multi-field structured payloads, returns the structured ``_arr``
        unchanged.
        """
        arr = self._arr
        if arr.dtype.names == ("value",):
            return arr["value"]
        return arr

    @property
    def raw_payload(self) -> NDArray[NpStructT]:
        """The backing ``_arr``. ``.tobytes()`` produces the wire payload."""
        return self._arr

    # ------------------------------------------------------------------
    # DataFrame
    # ------------------------------------------------------------------

    def to_dataframe(self, *, decode_enums: bool = True) -> pd.DataFrame:
        """Convert to a DataFrame. Works on both 0-D (1 row) and 1-D (N rows) ``_arr``."""
        arr = np.atleast_1d(self._arr)
        cls = type(self)
        repr_fields = self._repr_fields

        # Bitfield path — at least one repr field is a bit/group descriptor.
        has_bitfield = any(
            isinstance(
                inspect.getattr_static(cls, f, None), _SCALAR_BITFIELD_TYPES + _BATCH_BITFIELD_TYPES
            )
            for f in repr_fields
        )
        if has_bitfield:
            cols: dict[str, object] = {}
            value_col = arr["value"]
            for f in repr_fields:
                desc = inspect.getattr_static(cls, f, None)
                if isinstance(desc, _GROUP_TYPES):
                    raw = (value_col & desc._mask) >> desc._shift
                    if decode_enums:
                        codes = desc._code_lookup[raw]
                        cols[f] = pd.Categorical.from_codes(codes, categories=desc._categories)
                    else:
                        cols[f] = raw
                elif isinstance(desc, _FLAG_TYPES):
                    cols[f] = (value_col & desc._mask) != 0
                else:
                    # Custom property / hand-written field. Lift via atleast_1d
                    # so 0-D scalars become 1-row columns.
                    cols[f] = np.atleast_1d(getattr(self, f))
            return pd.DataFrame(cols)

        # Structured path — walk dtype fields, expand sub-arrays.
        cols = {}
        names = self._dtype.names
        single_value_field = names == ("value",)
        for name in names:
            field_dtype, _ = self._dtype.fields[name]
            sub = arr[name]
            if field_dtype.subdtype is None:
                cols[name] = sub
            else:
                _, subshape = field_dtype.subdtype
                count = int(np.prod(subshape))
                flat = sub.reshape(len(arr), count)
                for i in range(count):
                    col = str(i) if single_value_field else f"{name}_{i}"
                    cols[col] = flat[:, i]
        return pd.DataFrame(cols)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return 1 if self._arr.ndim == 0 else len(self._arr)

    def _repr_kwargs(self) -> str:
        return ", ".join(f"{f}={getattr(self, f)!r}" for f in self._repr_fields)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._repr_kwargs()})"

    def __str__(self) -> str:
        return repr(self)


# ------------------------------------------------------------------
# Named scalar payload classes — one per PayloadType.
# These are the concrete types returned by RegisterU8, RegisterU16, etc.
# ------------------------------------------------------------------


class PayloadU8(PayloadBase[np.uint8]):
    _dtype: ClassVar = np.dtype("u1")


class PayloadU16(PayloadBase[np.uint16]):
    _dtype: ClassVar = np.dtype("<u2")


class PayloadU32(PayloadBase[np.uint32]):
    _dtype: ClassVar = np.dtype("<u4")


class PayloadU64(PayloadBase[np.uint64]):
    _dtype: ClassVar = np.dtype("<u8")


class PayloadS8(PayloadBase[np.int8]):
    _dtype: ClassVar = np.dtype("i1")


class PayloadS16(PayloadBase[np.int16]):
    _dtype: ClassVar = np.dtype("<i2")


class PayloadS32(PayloadBase[np.int32]):
    _dtype: ClassVar = np.dtype("<i4")


class PayloadS64(PayloadBase[np.int64]):
    _dtype: ClassVar = np.dtype("<i8")


class PayloadFloat(PayloadBase[np.float32]):
    _dtype: ClassVar = np.dtype("<f4")


# ------------------------------------------------------------------
# Array payload classes — one per PayloadType.
# Each message payload is a fixed-length array of the element type.
# Length is not stored on the class; pass it explicitly to the
# array-register factory (RegisterU16Array(addr, length=N)).
# ------------------------------------------------------------------


@final
class PayloadU8Array(PayloadBase[NDArray[np.uint8]]):
    _dtype: ClassVar = np.dtype("u1")


@final
class PayloadU16Array(PayloadBase[NDArray[np.uint16]]):
    _dtype: ClassVar = np.dtype("<u2")


@final
class PayloadU32Array(PayloadBase[NDArray[np.uint32]]):
    _dtype: ClassVar = np.dtype("<u4")


@final
class PayloadU64Array(PayloadBase[NDArray[np.uint64]]):
    _dtype: ClassVar = np.dtype("<u8")


@final
class PayloadS8Array(PayloadBase[NDArray[np.int8]]):
    _dtype: ClassVar = np.dtype("i1")


@final
class PayloadS16Array(PayloadBase[NDArray[np.int16]]):
    _dtype: ClassVar = np.dtype("<i2")


@final
class PayloadS32Array(PayloadBase[NDArray[np.int32]]):
    _dtype: ClassVar = np.dtype("<i4")


@final
class PayloadS64Array(PayloadBase[NDArray[np.int64]]):
    _dtype: ClassVar = np.dtype("<i8")


@final
class PayloadFloatArray(PayloadBase[NDArray[np.float32]]):
    _dtype: ClassVar = np.dtype("<f4")
