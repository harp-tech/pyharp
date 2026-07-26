import re

import numpy as np
import pytest
from harp.data import DatasetReader, parse_to_dataframe
from harp.device import create_device


def _records(cls, n, seed):
    dtype = cls.payload_class.dtype
    rng = np.random.default_rng(seed)
    raw = rng.integers(0, 128, size=n * dtype.itemsize, dtype=np.uint8)
    return raw.view(dtype).copy()


@pytest.fixture
def emitted_device(device_yml):
    # strict=False: the test device.yml uses a custom DataConverter we don't inject
    # here; native decoding is enough to exercise file resolution and parsing.
    return create_device(device_yml, strict=False)


@pytest.fixture
def dataset(emitted_device, tmp_path):
    """A dataset folder with three app registers; the first is timestamped."""
    dev = emitted_device
    name = dev.__name__
    addresses = [a for a in sorted(dev.REGISTER_MAP) if a >= 32][:3]
    specs = {}
    for i, address in enumerate(addresses):
        cls = dev.REGISTER_MAP[address]
        records = _records(cls, 5, seed=address)
        timestamped = i == 0
        timestamps = np.arange(5, dtype=np.float64) if timestamped else None
        buf = bytes(cls.format_bulk(records, timestamps=timestamps))
        (tmp_path / f"{name}_{address}.bin").write_bytes(buf)
        specs[address] = (cls, timestamped, buf)
    return dev, name, tmp_path, specs


def test_read_by_class_and_by_address(dataset):
    dev, _name, root, specs = dataset
    reader = DatasetReader(dev, root)
    for address, (cls, timestamped, buf) in specs.items():
        expected = parse_to_dataframe(cls, buf, timestamp=timestamped)
        assert reader.read(cls).equals(expected)
        assert reader.read(address).equals(expected)


def test_timestamp_is_auto_detected(dataset):
    dev, _name, root, specs = dataset
    reader = DatasetReader(dev, root)
    for address, (_cls, timestamped, _buf) in specs.items():
        df = reader.read(address)
        assert ("timestamp" in df.columns) is timestamped


def test_read_all_keyed_by_register_name(dataset):
    dev, _name, root, specs = dataset
    reader = DatasetReader(dev, root)
    frames = reader.read_all()
    assert set(frames) == {cls.__name__ for cls, _ts, _buf in specs.values()}
    for cls, _timestamped, _buf in specs.values():
        assert frames[cls.__name__].equals(reader.read(cls.address))


def test_suffix_chunks_are_concatenated(emitted_device, tmp_path):
    dev = emitted_device
    name = dev.__name__
    address = next(a for a in sorted(dev.REGISTER_MAP) if a >= 32)
    cls = dev.REGISTER_MAP[address]
    chunk0 = bytes(cls.format_bulk(_records(cls, 3, seed=1)))
    chunk1 = bytes(cls.format_bulk(_records(cls, 2, seed=2)))
    (tmp_path / f"{name}_{address}_0.bin").write_bytes(chunk0)
    (tmp_path / f"{name}_{address}_1.bin").write_bytes(chunk1)

    reader = DatasetReader(dev, tmp_path)
    combined = parse_to_dataframe(cls, chunk0 + chunk1, timestamp=False)
    assert reader.read(cls).reset_index(drop=True).equals(combined)
    # A specific chunk can still be selected by suffix.
    only0 = parse_to_dataframe(cls, chunk0, timestamp=False)
    assert reader.read(cls, suffix="0").equals(only0)


def test_non_device_raises_on_register_access(dataset):
    _dev, _name, root, _specs = dataset
    # Registers are derived lazily; a non-Device fails when they are accessed.
    reader = DatasetReader(object, root)
    with pytest.raises(AttributeError, match="REGISTER_MAP"):
        _ = reader.registers


def test_explicit_name_overrides(dataset):
    dev, name, root, _specs = dataset
    reader = DatasetReader(dev, root, name=name)
    assert isinstance(reader, DatasetReader)
    assert reader.name == name


def test_missing_register_file_raises(dataset):
    dev, _name, root, _specs = dataset
    reader = DatasetReader(dev, root)
    # WhoAmI (address 0) is in the map but has no file in this dataset.
    with pytest.raises(FileNotFoundError):
        reader.read(0)


def test_unknown_address_raises(dataset):
    dev, _name, root, _specs = dataset
    reader = DatasetReader(dev, root)
    with pytest.raises(KeyError):
        reader.read(9999)


def test_custom_file_resolver_supports_alternative_layout(emitted_device, tmp_path):
    dev = emitted_device
    addresses = [a for a in sorted(dev.REGISTER_MAP) if a >= 32][:2]
    expected = {}
    for address in addresses:
        cls = dev.REGISTER_MAP[address]
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

    reader = DatasetReader(dev, tmp_path, resolver=resolver)
    assert set(reader.files) == set(addresses)
    frames = reader.read_all()
    assert set(frames) == set(expected)
    for register_name, df in frames.items():
        assert df.equals(expected[register_name])


def test_files_property_lists_discovered_bins(dataset):
    dev, _name, root, specs = dataset
    reader = DatasetReader(dev, root)
    assert set(reader.files) == set(specs)


def test_read_all_registers_of_mock_device(emitted_device, tmp_path):
    """Write one .bin per register of the device.yml device, then read them all back."""
    dev = emitted_device
    name = dev.__name__
    expected = {}
    for address, cls in dev.REGISTER_MAP.items():
        records = _records(cls, 4, seed=address)
        # Alternate timestamped/untimestamped to exercise both parse paths.
        timestamped = address % 2 == 0
        timestamps = np.arange(4, dtype=np.float64) if timestamped else None
        buf = bytes(cls.format_bulk(records, timestamps=timestamps))
        (tmp_path / f"{name}_{address}.bin").write_bytes(buf)
        expected[cls.__name__] = parse_to_dataframe(cls, buf, timestamp=timestamped)

    reader = DatasetReader(dev, tmp_path)
    frames = reader.read_all()

    assert set(reader.files) == set(dev.REGISTER_MAP)
    assert set(frames) == set(expected)
    assert len(frames) == len(dev.REGISTER_MAP)
    for register_name, df in frames.items():
        assert len(df) == 4
        assert df.equals(expected[register_name])


def test_reader_derives_name_and_registers_from_device(dataset):
    dev, name, root, _specs = dataset
    reader = DatasetReader(dev, root)
    assert reader.device is dev
    assert reader.name == name
    assert reader.registers == dev.REGISTER_MAP
