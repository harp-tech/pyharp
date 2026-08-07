import re
from collections.abc import Callable, Mapping
from datetime import datetime
from os import PathLike
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
from harp.device import create_module
from harp.protocol import RegisterBase
from harp.protocol._constants import _TIMESTAMP_FLAG

from ._reader import parse_to_dataframe

RegisterKey = type[RegisterBase[Any]] | int

FileNameResolver = Callable[[Path, str], Mapping[int, list[Path]]]

#: Default filename of the device schema looked up inside a dataset folder.
DEVICE_SCHEMA_FILENAME = "device.yml"


def default_file_resolver(root: Path, name: str) -> dict[int, list[Path]]:
    """Harp file format resolver: map address -> sorted ``<name>_<address>...`` files."""
    pattern = re.compile(rf"^{re.escape(name)}_(\d+)(?:_.*)?$")
    files: dict[int, list[Path]] = {}
    for path in sorted(root.glob("*.bin")):
        match = pattern.match(path.stem)
        if match is not None:
            files.setdefault(int(match.group(1)), []).append(path)
    return files


class DatasetReader:
    """Reader over a de-multiplexed Harp dataset folder.

    Construct from a device module and a dataset folder, then read a register's
    frames into a DataFrame by register class or by address::

        reader = DatasetReader(behavior, "session.harp")
        df = reader.read(behavior.AnalogData)  # by register class
        df = reader.read(44)                   # by address
        everything = reader.read_all()         # {register_name: DataFrame}

    ``module`` is a device module -- a generated device package, or one built from a
    schema with :func:`~harp.device.create_module`. Its ``REGISTER_MAP`` and
    ``__name__`` are read on demand. ``name`` overrides the ``<DeviceName>`` file
    prefix, which defaults to the module name.

    File resolution defaults to the Harp file format: ``<name>_<address>.bin`` and,
    when a register was logged as several ``<name>_<address>_<suffix>.bin`` chunks,
    they are concatenated in filename order. Pass ``resolver`` (a :data:`FileResolver`)
    to support an alternative on-disk layout.
    """

    def __init__(
        self,
        module: ModuleType,
        root: str | PathLike[str],
        *,
        name: str | None = None,
        resolver: FileNameResolver = default_file_resolver,
    ) -> None:
        self._module = module
        self._root = Path(root)
        self._name_override = name
        self._resolver = resolver
        self._files = dict(self._resolver(self._root, self.name))

    @property
    def root(self) -> Path:
        """The dataset folder being read."""
        return self._root

    @property
    def module(self) -> ModuleType:
        """The device module this reader parses against."""
        return self._module

    @property
    def name(self) -> str:
        """The ``<DeviceName>`` prefix used to match binary files."""
        return self._name_override or self._module.__name__

    @property
    def registers(self) -> Mapping[int, type[RegisterBase[Any]]]:
        """The module's address -> register-class map (its ``REGISTER_MAP``)."""
        return self._module.REGISTER_MAP

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
        """Read one register's data into a DataFrame.

        ``register`` is a register class or an address. ``suffix`` selects a single
        ``<name>_<address>_<suffix>.bin`` chunk (default: concatenate every chunk
        for the address). ``timestamp`` defaults to ``None`` — auto-detect from the
        frame's payload-type bit; pass ``True``/``False`` to force. ``epoch`` makes
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

        Files whose address is not in the device's registers are skipped.
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
            raise KeyError(f"No register at address {register} in this device's map.")
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
    strict: bool = True,
) -> DatasetReader:
    """Build a :class:`DatasetReader` for a dataset folder, device and all.

    Convenience wrapper that finds the device schema inside ``root`` (``device.yml``
    by default), builds its module with :func:`~harp.device.create_module`, and
    returns a reader ready to :meth:`~DatasetReader.read`::

        reader = create_dataset_reader("session.harp")
        df = reader.read(44)

    ``schema`` points at the schema file explicitly when it isn't ``root/device.yml``.
    ``converters`` and ``strict`` are forwarded to :func:`~harp.device.create_module`
    for custom ``interfaceType`` decoding; ``name`` and ``resolver`` are forwarded to
    :class:`DatasetReader`. Use ``DatasetReader(module, root)`` directly when you
    already have a (e.g. pre-generated) device module.
    """
    root_path = Path(root)
    schema_path = Path(schema) if schema is not None else root_path / DEVICE_SCHEMA_FILENAME
    if not schema_path.is_file():
        raise FileNotFoundError(
            f"No device schema at '{schema_path}'. Pass schema= to point at a device.yml, "
            f"or build the module yourself and use DatasetReader(module, root)."
        )
    module = create_module(schema_path.read_text(), converters=converters, strict=strict)
    return DatasetReader(module, root_path, name=name, resolver=resolver)
