from typing import ClassVar

import pytest
from harp.device import CoreRegisters, Device, create_device
from harp.protocol import RegisterU16

from .converters import DataConverter

CONVERTERS = {"DataConverter": DataConverter()}


class Counter(RegisterU16):
    address: ClassVar[int] = 40


class _StaticRegisters(CoreRegisters):
    Counter = Counter


class StaticDevice(Device[_StaticRegisters]):
    __whoami__ = 42
    registers = _StaticRegisters()


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
    by_address = test_device.registers.by_address
    assert by_address[33].__name__ == "AnalogData"
    assert by_address[103].__name__ == "EncoderMode"


def test_registers_include_core(test_device):
    regs = test_device.registers
    assert regs.WhoAmI.address == 0  # core register, always merged in
    assert regs.AnalogData.address == 33  # device-specific
    assert regs.by_address[0].__name__ == "WhoAmI"


def test_unknown_register_name_raises(test_device):
    with pytest.raises(AttributeError, match="Nonexistent"):
        _ = test_device.registers.Nonexistent


def test_registers_membership_is_by_register_class(test_device):
    from harp.device import WhoAmI

    regs = test_device.registers
    assert WhoAmI in regs  # register-class membership (core, merged in)
    assert regs.AnalogData in regs  # device-specific
    assert "WhoAmI" not in regs  # not by name
    assert 0 not in regs  # not by address


def test_registers_iterates_register_classes(test_device):
    regs = test_device.registers
    assert set(regs) == set(regs.by_address.values())
    assert len(regs) == len(regs.by_address)


def test_static_device_subclass_derives_registers():
    from harp.device import WhoAmI

    assert StaticDevice.__whoami__ == 42
    assert StaticDevice.registers.Counter is Counter  # device register, by name
    assert StaticDevice.registers.WhoAmI is WhoAmI  # common register, inherited
    assert Counter in StaticDevice.registers  # membership by register class
    assert StaticDevice.registers.by_address[40] is Counter


def test_device_register_overrides_core_on_clash():
    # A device register at a core address wins over the merged-in common one.
    Dev = create_device(
        "device: Clash\nregisters:\n  Shadow: {address: 0, type: U32, access: Read}\n"
    )
    assert Dev.registers.by_address[0].__name__ == "Shadow"
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
