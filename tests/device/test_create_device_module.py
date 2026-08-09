import sys
import types

import pytest
from harp.device import DeviceModule, create_device_module

from .converters import DataConverter

CONVERTERS = {"DataConverter": DataConverter()}


@pytest.fixture
def test_module(device_yml):
    return create_device_module(device_yml, converters=CONVERTERS)


def test_returns_module_named_after_schema(test_module):
    assert isinstance(test_module, types.ModuleType)
    assert test_module.__name__ == "Tests"


def test_returns_a_device_module(test_module):
    # The subclass is what declares REGISTER_MAP, WHO_AM_I and the register names,
    # so a linter can resolve them on a module built at runtime.
    assert isinstance(test_module, DeviceModule)


def test_whoami_defaults_to_zero_when_absent(test_module):
    # device.yml (application-device metadata) omits whoAmI.
    assert test_module.WHO_AM_I == 0


def test_whoami_from_schema():
    mod = create_device_module(
        "device: D\nwhoAmI: 1216\nregisters:\n  Foo: {address: 40, type: U16, access: Read}\n"
    )
    assert mod.WHO_AM_I == 1216


def test_registers_are_reachable_by_name(test_module):
    assert test_module.AnalogData.address == 33
    assert test_module.EncoderMode.address == 103


def test_registers_are_reachable_by_address(test_module):
    reg_map = test_module.REGISTER_MAP
    assert reg_map[33].__name__ == "AnalogData"
    assert reg_map[103].__name__ == "EncoderMode"


def test_register_map_spreads_core(test_module):
    reg_map = test_module.REGISTER_MAP
    assert reg_map[0].__name__ == "WhoAmI"  # core register, always spread in
    assert reg_map[33].__name__ == "AnalogData"  # device-specific
    assert reg_map[103].__name__ == "EncoderMode"


def test_core_registers_are_reachable_by_name(test_module):
    from harp.device import WhoAmI

    assert test_module.WhoAmI is WhoAmI  # the very same class, not a copy


def test_unknown_name_raises_attribute_error(test_module):
    # The message names the module and the register, since a schema-built module
    # cannot offer the name in an editor.
    with pytest.raises(AttributeError, match="'Tests' has no register named 'Nonexistent'"):
        _ = test_module.Nonexistent


def test_name_and_address_views_agree(test_module):
    # Both views index one set of classes, so they can never disagree about which
    # register sits at an address.
    registers = {cls.__name__: cls for cls in test_module.REGISTER_MAP.values()}
    assert len(registers) == len(test_module.REGISTER_MAP)  # no two names per address
    for name, cls in registers.items():
        assert getattr(test_module, name) is cls
        assert cls.address in test_module.REGISTER_MAP


def test_device_register_overrides_core_on_clash():
    # A device register at a core address wins over the spread-in common one, and
    # displaces it from the name view too, so the two views stay consistent.
    mod = create_device_module(
        "device: Clash\nregisters:\n  Shadow: {address: 0, type: U32, access: Read}\n"
    )
    assert mod.REGISTER_MAP[0].__name__ == "Shadow"
    assert mod.Shadow.address == 0
    assert not hasattr(mod, "WhoAmI")  # the common register it replaced is gone


def test_device_register_overrides_core_on_name_clash():
    # Same rule the other way round: the schema claiming a common *name* displaces
    # the common register entirely, rather than leaving the address view stale.
    mod = create_device_module(
        "device: Clash\nregisters:\n  WhoAmI: {address: 40, type: U16, access: Read}\n"
    )
    assert mod.WhoAmI.address == 40
    assert 0 not in mod.REGISTER_MAP


def test_headerless_fragment_builds_default_module():
    # A register-only fragment is a valid (nameless) device; name falls back to "Device".
    mod = create_device_module("registers:\n  Foo: {address: 40, type: U16, access: Read}\n")
    assert mod.__name__ == "Device"
    assert mod.WHO_AM_I == 0
    assert mod.REGISTER_MAP[40].__name__ == "Foo"
    assert mod.Foo.address == 40


def test_all_covers_registers_and_module_constants(test_module):
    exported = set(test_module.__all__)
    assert {"REGISTER_MAP", "WHO_AM_I"} <= exported
    assert {"AnalogData", "EncoderMode", "WhoAmI"} <= exported
    assert exported - {"REGISTER_MAP", "WHO_AM_I"} == {
        cls.__name__ for cls in test_module.REGISTER_MAP.values()
    }


def test_module_is_not_registered_in_sys_modules(test_module):
    # Two schemas may share a device name, so the module is handed back unbound.
    assert sys.modules.get(test_module.__name__) is not test_module


def test_emitted_registers_carry_the_module_name(test_module):
    assert test_module.AnalogData.__module__ == "Tests"


def test_emitted_registers_are_usable(test_module):
    reg = test_module.AnalogData
    # The emitted register class round-trips through the Device.read/write frame path.
    frame = reg.format(
        reg.payload_class(Analog0=1.0, Analog1=2.0, Analog2=3.0, Accelerometer=[4, 5, 6])
    )
    assert isinstance(frame, (bytes, bytearray))
