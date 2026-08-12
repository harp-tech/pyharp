from harp.device._schema import DeviceModel, PayloadType, parse_device_schema


def test_parse_full_device(device_yml):
    m = parse_device_schema(device_yml)
    assert isinstance(m, DeviceModel)
    assert m.device == "Tests"
    assert m.whoAmI is None  # this application-device metadata omits whoAmI
    assert "AnalogData" in m.registers
    ad = m.registers["AnalogData"]
    assert ad.type is PayloadType.Float
    assert ad.length == 6
    assert list(ad.payloadSpec) == ["Analog0", "Analog1", "Analog2", "Accelerometer"]


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


def test_parse_common_registers(common_yml):
    c = parse_device_schema(common_yml)
    assert c.device is None
    assert "WhoAmI" in c.registers
    # Off/On group-mask keys must stay strings (YAML 1.1 would coerce to bool).
    assert {k: int(v) for k, v in c.groupMasks["LedState"].values.items()} == {"Off": 0, "On": 1}
    # 'None' bit name stays a string, not YAML null.
    assert "None" in c.bitMasks["ResetFlags"].bits


def test_bool_values_preserved(common_yml):
    c = parse_device_schema(common_yml)
    assert c.registers["TimestampSeconds"].volatile is True


def test_access_list_and_scalar(common_yml):
    c = parse_device_schema(common_yml)
    # TimestampSeconds has a list access [Read, Write, Event]; WhoAmI a scalar.
    assert isinstance(c.registers["TimestampSeconds"].access, list)
