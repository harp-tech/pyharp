import re
from collections.abc import Callable, Mapping
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any, Generic, TypeVar

import pandas as pd
from harp.device.schema import (
    DeviceModule,
    DeviceModuleLike,
    create_device_module,
    parse_device_schema,
)
from harp.protocol import RegisterBase
from harp.protocol._constants import _TIMESTAMP_FLAG

from ._reader import parse_to_dataframe

M = TypeVar("M", bound=DeviceModuleLike)

RegisterKey = type[RegisterBase[Any]] | int

FileNameResolver = Callable[[Path, str], Mapping[int, list[Path]]]

DEVICE_SCHEMA_FILENAME = "device.yml"
"""Default filename of the device schema looked up inside a dataset folder."""


def default_file_resolver(root: Path, name: str) -> dict[int, list[Path]]:
    """Harp file format resolver: map address -> sorted ``<name>_<address>...`` files."""
    pattern = re.compile(rf"^{re.escape(name)}_(\d+)(?:_.*)?$")
    files: dict[int, list[Path]] = {}
    for path in sorted(root.glob("*.bin")):
        match = pattern.match(path.stem)
        if match is not None:
            files.setdefault(int(match.group(1)), []).append(path)
    return files


class DatasetReader(Generic[M]):
    """Reader over a de-multiplexed Harp dataset folder.

    Construct from a device module and a dataset folder, then read the
    frames of a register into a DataFrame by register class or by address::

        reader = DatasetReader(behavior, "session.harp")
        df = reader.read(behavior.AnalogData)  # by register class
        df = reader.read(44)                   # by address
        everything = reader.read_all()         # {register_name: DataFrame}

    ``device_module`` is a device module -- a generated device package, or one built from a
    schema with :func:`~harp.device.schema.create_device_module`. Its ``REGISTER_MAP`` is
    read on demand.

    The files are matched by a ``<DeviceName>`` prefix, taken from the ``DEVICE_NAME``
    declared by the module. Pass ``name`` to override it, or to supply one when the module
    declares an empty name.

    When the folder carries a ``device.yml`` and the module declares an identity, their
    ``whoAmI`` values are checked against each other. A module paired with the wrong
    folder then fails here rather than decoding the files against the wrong register
    map. ``validate`` turns off every check the reader performs, so a folder whose
    ``device.yml`` is damaged can be read with a module obtained elsewhere.

    The reader is typed on the module it was given, so registers stay reachable through
    :attr:`device_module` at whatever precision that module offers.

    File resolution defaults to the Harp file format: ``<name>_<address>.bin`` and,
    when a register was logged as several ``<name>_<address>_<suffix>.bin`` chunks,
    they are concatenated in filename order. Pass ``resolver`` (a :data:`FileResolver`)
    to support an alternative on-disk layout.
    """

    def __init__(
        self,
        device_module: M,
        root: str | PathLike[str],
        *,
        name: str | None = None,
        resolver: FileNameResolver = default_file_resolver,
        validate: bool = True,
    ) -> None:
        self._device_module = device_module
        self._root = Path(root)
        self._name_override = name
        self._resolver = resolver
        self._name = self._resolve_name()
        self._files = dict(self._resolver(self._root, self._name))
        if validate:
            self._validate_whoami()

    @property
    def root(self) -> Path:
        """The dataset folder being read."""
        return self._root

    @property
    def device_module(self) -> M:
        """The device module this reader parses against, as the type it was given.

        A generated package resolves each register to its own class; one built by
        :func:`~harp.device.schema.create_device_module` resolves them collectively,
        the same ceiling as reaching it directly.
        """
        return self._device_module

    @property
    def name(self) -> str:
        """The ``<DeviceName>`` prefix used to match binary files."""
        return self._name

    def _validate_whoami(self) -> None:
        expected = self._device_module.WHO_AM_I
        if expected == 0:
            return
        path = self._root / DEVICE_SCHEMA_FILENAME
        if not path.is_file():
            return
        try:
            actual = parse_device_schema(path.read_bytes()).whoAmI
        except ValueError:
            return
        if actual is None or int(actual) == expected:
            return
        raise ValueError(
            f"WhoAmI mismatch: {self._name} expects 0x{expected:04x} but the schema in "
            f"{self._root} declares 0x{int(actual):04x}."
        )

    def _resolve_name(self) -> str:
        if self._name_override is not None:
            return self._name_override
        declared = self._device_module.DEVICE_NAME
        if declared:
            return declared
        raise ValueError(
            f"The device module declares an empty DEVICE_NAME, so it cannot name the "
            f"files under {self._root}. Pass name= with the file prefix to read."
        )

    @property
    def registers(self) -> Mapping[int, type[RegisterBase[Any]]]:
        """The address -> register-class map the module carries as ``REGISTER_MAP``."""
        return self._device_module.REGISTER_MAP

    @property
    def files(self) -> Mapping[int, list[Path]]:
        """The discovered address -> binary file(s) present under :attr:`root`."""
        return self._files

    def read(
        self,
        register: RegisterKey,
        *,
        suffix: str | None = None,
        timestamp: bool | None = None,
        epoch: datetime | None = None,
        message_type: bool = False,
        decode_enums: bool = True,
        demux_bit_masks: bool = False,
    ) -> pd.DataFrame:
        """Read the data of one register into a DataFrame.

        ``register`` is a register class or an address. ``suffix`` selects a single
        ``<name>_<address>_<suffix>.bin`` chunk (default: concatenate every chunk
        for the address). ``timestamp`` defaults to ``None``, auto-detecting from the
        payload-type bit of the frame; pass ``True``/``False`` to force. ``epoch`` makes
        the ``"Time"`` index absolute (e.g. :data:`~harp.data.REFERENCE_EPOCH`). The
        remaining options match :func:`~harp.data.parse_to_dataframe`.
        """
        cls, address = self._resolve(register)
        paths = self._resolve_files(address, suffix)
        raw = b"".join(p.read_bytes() for p in paths)
        ts = self._first_frame_timestamped(raw) if timestamp is None else timestamp
        return parse_to_dataframe(
            cls,
            raw,
            timestamp=ts,
            epoch=epoch,
            message_type=message_type,
            decode_enums=decode_enums,
            demux_bit_masks=demux_bit_masks,
        )

    def read_all(
        self,
        *,
        timestamp: bool | None = None,
        epoch: datetime | None = None,
        message_type: bool = False,
        decode_enums: bool = True,
        demux_bit_masks: bool = False,
    ) -> dict[str, pd.DataFrame]:
        """Read every register that has a file present, keyed by register name.

        Files whose address is not among the device registers are skipped.
        Options are forwarded to :meth:`read`.
        """
        registers = self.registers
        out: dict[str, pd.DataFrame] = {}
        for address in sorted(self._files):
            cls = registers.get(address)
            if cls is None:
                continue
            out[cls.__name__] = self.read(
                address,
                timestamp=timestamp,
                epoch=epoch,
                message_type=message_type,
                decode_enums=decode_enums,
                demux_bit_masks=demux_bit_masks,
            )
        return out

    def _resolve(self, register: RegisterKey) -> tuple[type[RegisterBase[Any]], int]:
        if isinstance(register, type):
            return register, register.address
        cls = self.registers.get(register)
        if cls is None:
            raise KeyError(f"No register at address {register} in the map of this device.")
        return cls, register

    def _resolve_files(self, address: int, suffix: str | None) -> list[Path]:
        paths = self._files.get(address)
        if not paths:
            raise FileNotFoundError(
                f"No data file for register address {address} under {self._root} "
                f"(expected '{self.name}_{address}[_<suffix>].bin')."
            )
        if suffix is not None:
            paths = [p for p in paths if p.stem.endswith(f"_{suffix}")]
            if not paths:
                raise FileNotFoundError(
                    f"No '_{suffix}' chunk for register address {address} under {self._root}."
                )
        return paths

    @staticmethod
    def _first_frame_timestamped(raw: bytes) -> bool:
        """Whether the first frame carries a timestamp (payload-type bit ``0x10``)."""
        return len(raw) > 4 and bool(raw[4] & _TIMESTAMP_FLAG)


def create_dataset_reader(
    root: str | PathLike[str],
    *,
    schema: str | PathLike[str] | None = None,
    name: str | None = None,
    resolver: FileNameResolver = default_file_resolver,
    converters: Mapping[str, Any] | None = None,
    require_converters: bool = True,
    validate: bool = True,
) -> DatasetReader[DeviceModule]:
    """Build a :class:`DatasetReader` for a dataset folder, device and all.

    Convenience wrapper that finds the device schema inside ``root`` (``device.yml``
    by default), builds its module with :func:`~harp.device.schema.create_device_module`, and
    returns a reader ready to :meth:`~DatasetReader.read`::

        reader = create_dataset_reader("session.harp")
        df = reader.read(44)

    ``schema`` points at the schema file explicitly when it isn't ``root/device.yml``.
    ``converters`` and ``require_converters`` are forwarded to
    :func:`~harp.device.schema.create_device_module` for custom ``interfaceType``
    decoding; ``name``, ``resolver`` and ``validate`` are forwarded to
    :class:`DatasetReader`. Use ``DatasetReader(device_module, root)`` directly given a
    device module already in hand, for example a pre-generated one.

    Note ``validate`` cannot rescue a damaged ``device.yml`` here, since the module is
    built from that same file and fails before the reader exists. Reading such a folder
    means supplying a module obtained elsewhere.
    """
    root_path = Path(root)
    schema_path = Path(schema) if schema is not None else root_path / DEVICE_SCHEMA_FILENAME
    if not schema_path.is_file():
        raise FileNotFoundError(
            f"No device schema at '{schema_path}'. Pass schema= to point at a device.yml, "
            f"or build the device module yourself and use DatasetReader(device_module, root)."
        )
    device_module = create_device_module(
        schema_path.read_text(), converters=converters, require_converters=require_converters
    )
    return DatasetReader(device_module, root_path, name=name, resolver=resolver, validate=validate)
