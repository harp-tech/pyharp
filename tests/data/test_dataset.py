import re

import numpy as np
import pandas as pd
import pytest
from harp.data import (
    REFERENCE_EPOCH,
    DatasetReader,
    create_dataset_reader,
    parse_to_dataframe,
)
from harp.device.core import TimestampSeconds, WhoAmI
from harp.device.schema import create_device_module


def _records(cls, n, seed):
    dtype = cls.payload_class.payload_dtype
    rng = np.random.default_rng(seed)
    raw = rng.integers(0, 128, size=n * dtype.itemsize, dtype=np.uint8)
    return raw.view(dtype).copy()


@pytest.fixture
def emitted_module(device_yml):
    # strict=False: the test device.yml uses a custom DataConverter we don't inject
    # here; native decoding is enough to exercise file resolution and parsing.
    return create_device_module(device_yml, strict=False)


@pytest.fixture
def dataset(emitted_module, tmp_path):
    """A dataset folder with three app registers; the first is timestamped."""
    mod = emitted_module
    name = mod.__name__
    addresses = [a for a in sorted(mod.REGISTER_MAP) if a >= 32][:3]
    specs = {}
    for i, address in enumerate(addresses):
        cls = mod.REGISTER_MAP[address]
        records = _records(cls, 5, seed=address)
        timestamped = i == 0
        timestamps = np.arange(5, dtype=np.float64) if timestamped else None
        buf = bytes(cls.format_bulk(records, timestamps=timestamps))
        (tmp_path / f"{name}_{address}.bin").write_bytes(buf)
        specs[address] = (cls, timestamped, buf)
    return mod, name, tmp_path, specs


def test_read_by_class_and_by_address(dataset):
    mod, _name, root, specs = dataset
    reader = DatasetReader(mod, root)
    for address, (cls, timestamped, buf) in specs.items():
        expected = parse_to_dataframe(cls, buf, timestamp=timestamped)
        assert reader.read(cls).equals(expected)
        assert reader.read(address).equals(expected)


def test_read_by_name_from_module(dataset):
    mod, _name, root, specs = dataset
    reader = DatasetReader(mod, root)
    for address, (cls, _timestamped, _buf) in specs.items():
        # The register reached by name off the module is the one at that address.
        assert reader.read(getattr(mod, cls.__name__)).equals(reader.read(address))


def test_reads_common_registers_not_named_by_module(emitted_module, tmp_path):
    """A device module names only its own registers, but a session folder also holds
    files for the common ones, so the reader must still decode those."""
    mod = emitted_module
    assert not hasattr(mod, "WhoAmI")  # imported from harp.device, not re-exported

    for cls in (WhoAmI, TimestampSeconds):
        records = _records(cls, 4, seed=cls.address)
        buf = bytes(cls.format_bulk(records))
        (tmp_path / f"{mod.__name__}_{cls.address}.bin").write_bytes(buf)

    reader = DatasetReader(mod, tmp_path)
    # By address, and by the class imported from harp.device, and in read_all.
    assert len(reader.read(WhoAmI.address)) == 4
    assert reader.read(WhoAmI).equals(reader.read(WhoAmI.address))
    assert set(reader.read_all()) == {"WhoAmI", "TimestampSeconds"}


def test_timestamp_is_auto_detected(dataset):
    mod, _name, root, specs = dataset
    reader = DatasetReader(mod, root)
    for address, (_cls, timestamped, _buf) in specs.items():
        df = reader.read(address)
        # Timestamped frames get a "Time" index; untimestamped keep a plain RangeIndex.
        assert (df.index.name == "Time") is timestamped


def test_time_index_is_float_seconds_without_epoch(dataset):
    mod, _name, root, specs = dataset
    reader = DatasetReader(mod, root)
    address = next(a for a, (_c, ts, _b) in specs.items() if ts)  # the timestamped register
    df = reader.read(address)
    assert df.index.name == "Time"
    assert list(df.index) == [0.0, 1.0, 2.0, 3.0, 4.0]  # arange(5) seconds from the fixture


def test_epoch_gives_absolute_datetime_index(dataset):
    mod, _name, root, specs = dataset
    reader = DatasetReader(mod, root)
    address = next(a for a, (_c, ts, _b) in specs.items() if ts)
    df = reader.read(address, epoch=REFERENCE_EPOCH)
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.name == "Time"
    # Harp seconds are measured from the reference epoch (timestamps were arange(5)).
    assert df.index[0] == pd.Timestamp(REFERENCE_EPOCH)
    assert df.index[2] == pd.Timestamp(REFERENCE_EPOCH) + pd.Timedelta(seconds=2)


def test_read_all_keyed_by_register_name(dataset):
    mod, _name, root, specs = dataset
    reader = DatasetReader(mod, root)
    frames = reader.read_all()
    assert set(frames) == {cls.__name__ for cls, _ts, _buf in specs.values()}
    for cls, _timestamped, _buf in specs.values():
        assert frames[cls.__name__].equals(reader.read(cls.address))


def test_suffix_chunks_are_concatenated(emitted_module, tmp_path):
    mod = emitted_module
    name = mod.__name__
    address = next(a for a in sorted(mod.REGISTER_MAP) if a >= 32)
    cls = mod.REGISTER_MAP[address]
    chunk0 = bytes(cls.format_bulk(_records(cls, 3, seed=1)))
    chunk1 = bytes(cls.format_bulk(_records(cls, 2, seed=2)))
    (tmp_path / f"{name}_{address}_0.bin").write_bytes(chunk0)
    (tmp_path / f"{name}_{address}_1.bin").write_bytes(chunk1)

    reader = DatasetReader(mod, tmp_path)
    combined = parse_to_dataframe(cls, chunk0 + chunk1, timestamp=False)
    assert reader.read(cls).reset_index(drop=True).equals(combined)
    # A specific chunk can still be selected by suffix.
    only0 = parse_to_dataframe(cls, chunk0, timestamp=False)
    assert reader.read(cls, suffix="0").equals(only0)


def test_non_module_raises_on_register_access(dataset):
    _mod, _name, root, _specs = dataset
    # Registers are derived lazily; anything without a REGISTER_MAP fails on access.
    reader = DatasetReader(object, root)
    with pytest.raises(AttributeError, match="REGISTER_MAP"):
        _ = reader.registers


def test_explicit_name_overrides(dataset):
    mod, name, root, _specs = dataset
    reader = DatasetReader(mod, root, name=name)
    assert isinstance(reader, DatasetReader)
    assert reader.name == name


def test_name_from_device_name_not_module_name(dataset):
    # The prefix follows DEVICE_NAME rather than __name__, so rebinding the module
    # does not change which files are read.
    mod, name, root, _specs = dataset
    mod.__name__ = "not_the_device_name"
    assert DatasetReader(mod, root).name == name


def test_name_discovered_without_device_name(dataset):
    # A device package published before DEVICE_NAME existed declares no name, so the
    # folder is the only remaining source.
    mod, name, root, _specs = dataset
    del mod.DEVICE_NAME
    assert DatasetReader(mod, root).name == name


def test_ambiguous_folder_raises(dataset):
    mod, name, root, specs = dataset
    del mod.DEVICE_NAME
    address = next(iter(specs))
    (root / f"Other_{address}.bin").write_bytes(b"")
    with pytest.raises(ValueError, match="Pass name=") as excinfo:
        DatasetReader(mod, root)
    # The message names what it found, so the caller knows what to choose between.
    assert name in str(excinfo.value)
    assert "Other" in str(excinfo.value)
    assert DatasetReader(mod, root, name=name).name == name


def test_empty_dataset_reads_empty(emitted_module, tmp_path):
    # A session that logged nothing is a dataset with no data, not a failure.
    reader = DatasetReader(emitted_module, tmp_path)
    assert reader.name == emitted_module.DEVICE_NAME
    assert reader.files == {}
    assert reader.read_all() == {}


def test_unresolvable_prefix_raises(emitted_module, tmp_path):
    # Nothing declares a name and nothing on disk suggests one, so no prefix can be
    # determined. This is the reader failing to be set up, not an empty dataset.
    del emitted_module.DEVICE_NAME
    with pytest.raises(ValueError, match="Pass name="):
        DatasetReader(emitted_module, tmp_path)


def test_chunked_files_discover_single_name(emitted_module, tmp_path):
    # A stem splits at its first address, so the chunk suffix of a multi-chunk register
    # stays out of the device name and one device is not discovered as several.
    mod = emitted_module
    name = mod.DEVICE_NAME
    address = next(a for a in sorted(mod.REGISTER_MAP) if a >= 32)
    cls = mod.REGISTER_MAP[address]
    for chunk in range(2):
        buf = bytes(cls.format_bulk(_records(cls, 2, seed=chunk)))
        (tmp_path / f"{name}_{address}_{chunk}.bin").write_bytes(buf)

    del mod.DEVICE_NAME
    assert DatasetReader(mod, tmp_path).name == name


def test_missing_register_file_raises(dataset):
    mod, _name, root, _specs = dataset
    reader = DatasetReader(mod, root)
    # WhoAmI (address 0) is in the map but has no file in this dataset.
    with pytest.raises(FileNotFoundError):
        reader.read(0)


def test_unknown_address_raises(dataset):
    mod, _name, root, _specs = dataset
    reader = DatasetReader(mod, root)
    with pytest.raises(KeyError):
        reader.read(9999)


def test_custom_file_resolver_supports_alternative_layout(emitted_module, tmp_path):
    mod = emitted_module
    addresses = [a for a in sorted(mod.REGISTER_MAP) if a >= 32][:2]
    expected = {}
    for address in addresses:
        cls = mod.REGISTER_MAP[address]
        buf = bytes(cls.format_bulk(_records(cls, 3, seed=address)))
        (tmp_path / f"reg{address}.bin").write_bytes(buf)  # not the Harp layout
        expected[cls.__name__] = parse_to_dataframe(cls, buf, timestamp=False)

    def resolver(root, _name):
        found = {}
        for path in sorted(root.glob("reg*.bin")):
            match = re.match(r"^reg(\d+)$", path.stem)
            if match is not None:
                found.setdefault(int(match.group(1)), []).append(path)
        return found

    reader = DatasetReader(mod, tmp_path, resolver=resolver)
    assert set(reader.files) == set(addresses)
    frames = reader.read_all()
    assert set(frames) == set(expected)
    for register_name, df in frames.items():
        assert df.equals(expected[register_name])


def test_files_property_lists_discovered_bins(dataset):
    mod, _name, root, specs = dataset
    reader = DatasetReader(mod, root)
    assert set(reader.files) == set(specs)


def test_read_all_registers_of_mock_device(emitted_module, tmp_path):
    """Write one .bin per register of the device.yml device, then read them all back."""
    mod = emitted_module
    name = mod.__name__
    expected = {}
    for address, cls in mod.REGISTER_MAP.items():
        records = _records(cls, 4, seed=address)
        # Alternate timestamped/untimestamped to exercise both parse paths.
        timestamped = address % 2 == 0
        timestamps = np.arange(4, dtype=np.float64) if timestamped else None
        buf = bytes(cls.format_bulk(records, timestamps=timestamps))
        (tmp_path / f"{name}_{address}.bin").write_bytes(buf)
        expected[cls.__name__] = parse_to_dataframe(cls, buf, timestamp=timestamped)

    reader = DatasetReader(mod, tmp_path)
    frames = reader.read_all()

    assert set(reader.files) == set(mod.REGISTER_MAP)
    assert set(frames) == set(expected)
    assert len(frames) == len(mod.REGISTER_MAP)
    for register_name, df in frames.items():
        assert len(df) == 4
        assert df.equals(expected[register_name])


def test_reader_derives_name_and_registers_from_module(dataset):
    mod, name, root, _specs = dataset
    reader = DatasetReader(mod, root)
    assert reader.device_module is mod
    assert reader.name == name
    assert reader.registers == mod.REGISTER_MAP


def test_create_dataset_reader_builds_module_from_device_yml(dataset, device_yml):
    mod, _name, root, specs = dataset
    (root / "device.yml").write_text(device_yml)
    # strict=False mirrors the emitted_module fixture (custom DataConverter not injected).
    reader = create_dataset_reader(root, strict=False)
    assert isinstance(reader, DatasetReader)
    # Reads match a reader built from an explicitly-generated module.
    reference = DatasetReader(mod, root)
    for address, (cls, _timestamped, _buf) in specs.items():
        assert reader.read(address).equals(reference.read(cls))


def test_create_dataset_reader_accepts_explicit_schema_path(dataset, device_yml, tmp_path):
    _mod, _name, root, specs = dataset
    schema_path = tmp_path / "elsewhere.yml"  # not inside the dataset folder
    schema_path.write_text(device_yml)
    reader = create_dataset_reader(root, schema=schema_path, strict=False)
    address = next(iter(specs))
    assert not reader.read(address).empty


def test_create_dataset_reader_missing_schema_raises(dataset):
    _mod, _name, root, _specs = dataset  # no device.yml written into the folder
    with pytest.raises(FileNotFoundError, match="device.yml"):
        create_dataset_reader(root)
