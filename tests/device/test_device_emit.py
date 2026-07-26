import pytest
from harp.device import Device, create_device

from .converters import DataConverter

CONVERTERS = {"DataConverter": DataConverter()}


@pytest.fixture
def test_device(device_yml):
    return create_device(device_yml, converters=CONVERTERS)


def test_returns_device_subclass(test_device):
    assert issubclass(test_device, Device)
    assert test_device.__name__ == "Tests"


def test_whoami_defaults_to_zero_when_absent(test_device):
    # device.yml (application-device metadata) omits whoAmI.
    assert test_device.__whoami__ == 0


def test_whoami_from_schema():
    Dev = create_device(
        "device: D\nwhoAmI: 1216\nregisters:\n  Foo: {address: 40, type: U16, access: Read}\n"
    )
    assert Dev.__whoami__ == 1216


def test_registers_are_reachable_by_name(test_device):
    regs = test_device.registers
    assert regs.AnalogData.address == 33
    assert regs.EncoderMode.address == 103


def test_registers_are_reachable_by_address(test_device):
    regs = test_device.registers
    assert regs[33].__name__ == "AnalogData"
    assert regs[103].__name__ == "EncoderMode"


def test_registers_include_core(test_device):
    regs = test_device.registers
    assert regs.WhoAmI.address == 0  # core register, always merged in
    assert regs.AnalogData.address == 33  # device-specific
    assert regs[0].__name__ == "WhoAmI"


def test_unknown_register_name_raises(test_device):
    with pytest.raises(AttributeError, match="Nonexistent"):
        _ = test_device.registers.Nonexistent


def test_device_register_overrides_core_on_clash():
    # A device register at a core address wins over the merged-in common one.
    Dev = create_device(
        "device: Clash\nregisters:\n  Shadow: {address: 0, type: U32, access: Read}\n"
    )
    assert Dev.registers[0].__name__ == "Shadow"
    assert Dev.registers.Shadow.address == 0


def test_headerless_fragment_builds_default_device():
    # A register-only fragment is a valid (nameless) device; name falls back to "Device".
    Dev = create_device("registers:\n  Foo: {address: 40, type: U16, access: Read}\n")
    assert Dev.__name__ == "Device"
    assert Dev.__whoami__ == 0
    assert Dev.registers.Foo.address == 40


def test_emitted_device_registers_are_usable(test_device):
    reg = test_device.registers.AnalogData  # reached by name
    # The emitted register class round-trips through the Device.read/write frame path.
    frame = reg.format(
        reg.payload_class(Analog0=1.0, Analog1=2.0, Analog2=3.0, Accelerometer=[4, 5, 6])
    )
    assert isinstance(frame, (bytes, bytearray))
