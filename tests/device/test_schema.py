import pytest
from pydantic import ValidationError

from harp.device.schema import parse_device_schema
from harp.device.schema._model import DeviceModel, PayloadType


def test_parse_full_device(device_yml):
    m = parse_device_schema(device_yml)
    assert isinstance(m, DeviceModel)
    assert m.device == "Tests"
    assert m.whoAmI is None  # this application-device metadata omits whoAmI
    assert m.description is None  # and omits a top-level description
    assert "AnalogData" in m.registers
    ad = m.registers["AnalogData"]
    assert ad.type is PayloadType.Float
    assert ad.length == 6
    assert list(ad.payloadSpec) == ["Analog0", "Analog1", "Analog2", "Accelerometer"]


def test_colliding_declaration_names_are_rejected():
    # Registers and masks are rendered into one namespace, so a name describing two of
    # them would leave whichever came last and silently lose the other.
    schema = (
        "device: Clash\n"
        "registers:\n"
        "  Mode: {address: 32, type: U8, access: Read, maskType: Mode}\n"
        "groupMasks:\n"
        "  Mode:\n"
        "    values:\n"
        "      Idle: {value: 0}\n"
    )
    with pytest.raises(ValidationError, match="both a register and a group mask"):
        parse_device_schema(schema)


def test_parse_fragment_yields_null_device():
    m = parse_device_schema("registers:\n  Foo: {address: 40, type: U16, access: Read}\n")
    assert isinstance(m, DeviceModel)
    assert m.device is None  # header-less fragment -> identity fields are None
    assert m.registers["Foo"].type is PayloadType.U16


def test_parse_bytes_decodes_as_utf8_regardless_of_locale():
    # A YAML stream declares its own encoding, so reading a schema as bytes decodes it
    # correctly where read_text() without an explicit encoding follows the locale.
    schema = (
        "registers:\n"
        "  Poke:\n"
        "    address: 40\n"
        "    type: U8\n"
        "    access: Read\n"
        "    description: µV threshold\n"
    )
    m = parse_device_schema(schema.encode("utf-8"))
    assert m.registers["Poke"].description == "µV threshold"
    assert (
        m.registers["Poke"].description == parse_device_schema(schema).registers["Poke"].description
    )


def test_reserved_word_mask_keys_stay_strings():
    # Off, On, Yes and No are booleans in YAML 1.1, so a 1.1 parser keys these values by
    # True and False.
    schema = (
        "registers:\n"
        "  Indicators: {address: 32, type: U8, access: Write, maskType: LedState}\n"
        "groupMasks:\n"
        "  LedState:\n"
        "    values:\n"
        "      Off: 0\n"
        "      On: 1\n"
    )
    m = parse_device_schema(schema)
    assert {k: int(v) for k, v in m.groupMasks["LedState"].values.items()} == {"Off": 0, "On": 1}


def test_parse_core_registers(core_yml):
    c = parse_device_schema(core_yml)
    assert "WhoAmI" in c.registers
    assert c.description  # the core metadata declares a top-level description
    # 'None' bit name stays a string, not YAML null.
    assert "None" in c.bitMasks["ResetFlags"].bits


def test_bool_values_preserved(core_yml):
    c = parse_device_schema(core_yml)
    assert c.registers["TimestampSeconds"].volatile is True


def test_access_list_and_scalar(core_yml):
    c = parse_device_schema(core_yml)
    # TimestampSeconds has a list access [Read, Write, Event]; WhoAmI a scalar.
    assert isinstance(c.registers["TimestampSeconds"].access, list)
