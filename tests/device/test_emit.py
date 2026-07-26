import zlib

import numpy as np
import pytest
from harp.data import parse_to_dataframe
from harp.protocol import HarpMessage

from harp.device._schema import UnknownConverterError, create_registers

from . import expected_core, expected_device
from .converters import DataConverter

CONVERTERS = {"DataConverter": DataConverter()}


@pytest.fixture
def device_registers(device_yml):
    return create_registers(device_yml, converters=CONVERTERS)


def _device_registers():
    # expected_device.Tests.__REGISTERS__ holds only the device-specific registers
    # (the ones the emitter builds from device.yml); the core ones are merged in
    # by Device automatically.
    return {cls.__name__: cls for cls in expected_device.Tests.__REGISTERS__}


def _layout(dt):
    """Name-agnostic structural signature: element dtype + offset per field, and itemsize.

    Ignores field names (we keep the yml's verbatim names; the generator
    snake_cases them) while still verifying the byte layout matches exactly.
    """
    if dt.names is None:
        return ("scalar", dt.str, dt.shape, dt.itemsize)
    return ("struct", dt.itemsize, tuple((dt.fields[n][0], dt.fields[n][1]) for n in dt.names))


# ---------------------------------------------------------------------------
# Device golden — layout/type parity with generator output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(_device_registers()))
def test_device_register_matches_generator_layout(name, device_registers):
    emitted = device_registers[name]
    expected = _device_registers()[name]
    assert emitted.address == expected.address
    assert emitted.payload_type == expected.payload_type
    assert _layout(emitted.payload_class.dtype) == _layout(expected.payload_class.dtype)


def test_device_emits_all_registers(device_registers):
    assert set(device_registers) == set(_device_registers())


# ---------------------------------------------------------------------------
# Verbatim naming — the yml is the single source of truth
# ---------------------------------------------------------------------------


def test_field_names_are_verbatim(device_registers):
    fields = device_registers["AnalogData"].payload_class.dtype.names
    assert fields == ("Analog0", "Analog1", "Analog2", "Accelerometer")


def test_enum_members_are_verbatim(device_registers):
    flags = device_registers["PortDIOSet"].payload_class._mro_descriptor("__value__")._enum
    # yml bit names are kept as-is (the generator would UPPER_SNAKE these).
    assert {"DIO0", "DIPort0", "TestDIPort1", "PortDIO1"} <= set(flags.__members__)


# ---------------------------------------------------------------------------
# Core golden — from protocol common.yml
# ---------------------------------------------------------------------------


def _core_expected():
    return {cls.__name__: cls for cls in expected_core.REGISTERS}


@pytest.mark.parametrize("name", sorted(_core_expected()))
def test_core_register_structural(name, common_yml):
    emitted = create_registers(common_yml)[name]
    expected = _core_expected()[name]
    assert emitted.address == expected.address
    assert emitted.payload_type == expected.payload_type
    assert emitted.payload_class.dtype.itemsize == expected.payload_class.dtype.itemsize
    if name == "DeviceName":
        # Generator enriches DeviceName to interfaceType: string; protocol's
        # common.yml does not, so only the layout size matches here.
        return
    assert _layout(emitted.payload_class.dtype) == _layout(expected.payload_class.dtype)


# ---------------------------------------------------------------------------
# Behavioural round-trips
# ---------------------------------------------------------------------------


def _roundtrip(reg, value):
    return reg.parse(HarpMessage.parse(reg.format(value)))


def test_whole_register_groupmask_unwraps_to_enum(device_registers):
    reg = device_registers["EncoderMode"]
    enum_cls = reg.payload_class._mro_descriptor("__value__")._enum
    parsed = _roundtrip(reg, enum_cls["Displacement"])
    assert parsed == enum_cls["Displacement"]
    assert isinstance(parsed, enum_cls)


def test_whole_register_bitmask_roundtrip(device_registers):
    reg = device_registers["PortDIOSet"]
    flags = reg.payload_class._mro_descriptor("__value__")._enum
    value = flags["DIO0"] | flags["DIO3"]
    assert _roundtrip(reg, value) == value


def test_struct_masked_members_roundtrip(device_registers):
    reg = device_registers["StartPulse"]
    payload_cls = reg.payload_class
    pwm = payload_cls._mro_descriptor("DigitalOutput")._enum
    # DigitalOutput is a 2-bit field (mask 0xC00); only Pwm0/Pwm1 fit it. This
    # matches the generator's output verbatim (GroupMask(enum=PwmPort, mask=0xC00)).
    payload = payload_cls(DigitalOutput=pwm["Pwm1"], PulseWidth=np.uint16(300))
    parsed = _roundtrip(reg, payload)
    assert parsed.DigitalOutput == pwm["Pwm1"]
    assert int(parsed.PulseWidth) == 300


def test_custom_converter_roundtrip(device_registers):
    reg = device_registers["CustomMemberConverter"]
    payload_cls = reg.payload_class
    parsed = _roundtrip(reg, payload_cls(Header=np.uint8(7), Data=-1234))
    assert int(parsed.Header) == 7
    assert int(parsed.Data) == -1234


# ---------------------------------------------------------------------------
# Converter registry
# ---------------------------------------------------------------------------


def test_unknown_converter_raises(device_yml):
    with pytest.raises(UnknownConverterError):
        create_registers(device_yml)  # CustomMemberConverter needs DataConverter


def test_non_strict_falls_back_to_native(device_yml):
    regs = create_registers(device_yml, strict=False)
    # Data decodes as the raw native element (u8[2]) rather than the custom int.
    reg = regs["CustomMemberConverter"]
    assert reg.payload_class.dtype.itemsize == 3


def test_converter_factory_receives_dsl_context(device_yml):
    seen = {}

    def factory(ctx):
        seen["name"], seen["span"], seen["interface_type"] = ctx.name, ctx.span, ctx.interface_type
        return DataConverter()

    regs = create_registers(device_yml, converters={"DataConverter": factory})
    parsed = _roundtrip(
        regs["CustomMemberConverter"],
        regs["CustomMemberConverter"].payload_class(Header=np.uint8(1), Data=42),
    )
    assert int(parsed.Data) == 42
    # the factory was handed the Data field's resolved DSL context
    assert seen == {"name": "Data", "span": 2, "interface_type": "int"}


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


def test_exclude_private_drops_private_registers():
    yml = (
        "registers:\n"
        "  Pub: {address: 40, type: U16, access: Read}\n"
        "  Priv: {address: 41, type: U16, access: Read, visibility: private}\n"
    )
    assert set(create_registers(yml)) == {"Pub", "Priv"}  # kept by default
    assert set(create_registers(yml, exclude_private=True)) == {"Pub"}


# ---------------------------------------------------------------------------
# Golden bulk round-trip — the emitted register and the generator oracle are
# wire- and dataframe-compatible for the same payload bytes (cross read/write).
# ---------------------------------------------------------------------------


def _random_records(dtype, n, seed):
    """``n`` deterministic records of ``dtype`` with random ASCII-range bytes.

    Bytes are held to 0..127 so every field varies while staying valid for any
    ``StringConverter`` member and free of float NaN/inf (which would defeat the
    value comparison); padding bytes are filled too but never read back.
    """
    rng = np.random.default_rng(seed)
    raw = rng.integers(0, 128, size=n * dtype.itemsize, dtype=np.uint8)
    return raw.view(dtype).copy()


@pytest.mark.parametrize("name", sorted(_device_registers()))
def test_emitted_register_bulk_matches_oracle(name, device_registers):
    emitted = device_registers[name]
    oracle = _device_registers()[name]
    records = _random_records(emitted.payload_class.dtype, 5, seed=zlib.crc32(name.encode()))

    # Cross-write: same address / payload_type / byte layout -> identical wire bytes.
    buf = bytes(emitted.format_bulk(records))
    assert buf == bytes(oracle.format_bulk(records))

    # Cross-read via harp.data: the shared bytes decode to equal frames through
    # either class. Enum labels and field names diverge (verbatim yml vs generator
    # snake_case), so compare raw codes by column position, not by name.
    df_emitted = parse_to_dataframe(emitted, buf, timestamp=False, decode_enums=False)
    df_oracle = parse_to_dataframe(oracle, buf, timestamp=False, decode_enums=False)
    df_oracle.columns = df_emitted.columns
    assert df_emitted.equals(df_oracle)
