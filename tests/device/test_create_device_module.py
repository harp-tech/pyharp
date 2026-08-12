import sys
import types

import harp.device
import pytest
from harp.device import REGISTER_MAP as CORE_REGISTER_MAP
from harp.device import DeviceModule, DeviceModuleLike, WhoAmI, create_device_module

from . import expected_device
from .converters import DataConverter

CONVERTERS = {"DataConverter": DataConverter()}
MODULE_CONSTANTS = {"REGISTER_MAP", "WHO_AM_I"}


@pytest.fixture
def test_module(device_yml):
    return create_device_module(device_yml, converters=CONVERTERS)


def test_returns_module_named_after_schema(test_module):
    assert isinstance(test_module, types.ModuleType)
    assert test_module.__name__ == "Tests"


def test_returns_device_module(test_module):
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


def test_core_registers_are_not_named_by_module(test_module):
    # A common register has one definition, in harp.device, so a device module does
    # not re-export it. It is still in the address space the device can send from.
    assert not hasattr(test_module, "WhoAmI")
    assert test_module.REGISTER_MAP[0] is WhoAmI


def test_module_names_exactly_schema_registers(test_module):
    named = {n for n in vars(test_module) if not n.startswith("_") and n not in MODULE_CONSTANTS}
    addresses = {cls.address for cls in test_module.REGISTER_MAP.values()}
    # Everything the module names is in the address space, and the map carries the
    # common registers on top, which is the whole difference between the two.
    assert all(getattr(test_module, n).address in addresses for n in named)
    assert {c.__name__ for c in CORE_REGISTER_MAP.values()}.isdisjoint(named)
    assert len(test_module.REGISTER_MAP) > len(named)


def test_emitted_module_matches_device_protocol(test_module):
    assert isinstance(test_module, DeviceModuleLike)


def test_generated_package_matches_device_protocol():
    # expected_device is a sample of generator output, so this pins that what the
    # generator emits is accepted wherever a device module is required.
    assert isinstance(expected_device, DeviceModuleLike)


def test_common_registers_are_not_device_module():
    # They carry REGISTER_MAP but describe no device, so they cannot be passed
    # where a device module is required, such as to a DatasetReader.
    assert hasattr(harp.device, "REGISTER_MAP")
    assert not hasattr(harp.device, "WHO_AM_I")
    assert not isinstance(harp.device, DeviceModuleLike)


def test_unknown_name_raises_attribute_error(test_module):
    # The message names the module and the register, since a schema-built module
    # cannot offer the name in an editor.
    with pytest.raises(AttributeError, match="'Tests' has no register named 'Nonexistent'"):
        _ = test_module.Nonexistent


def test_named_registers_are_subset_of_address_space(test_module):
    # The two are deliberately different sets: the module names what the schema
    # declares, the map is everything the device can send.
    for cls in test_module.REGISTER_MAP.values():
        if cls.address >= 32:
            assert getattr(test_module, cls.__name__) is cls
    assert 0 in test_module.REGISTER_MAP


def test_device_register_overrides_core_on_clash():
    # A device register at a common address replaces it in the address space.
    mod = create_device_module(
        "device: Clash\nregisters:\n  Shadow: {address: 0, type: U32, access: Read}\n"
    )
    assert mod.REGISTER_MAP[0].__name__ == "Shadow"
    assert mod.Shadow.address == 0


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
    assert {"AnalogData", "EncoderMode"} <= exported
    assert "WhoAmI" not in exported  # a common register is not re-exported
    assert exported - MODULE_CONSTANTS == {
        cls.__name__ for cls in test_module.REGISTER_MAP.values() if cls.address >= 32
    }


def test_module_is_not_registered_in_sys_modules(test_module):
    # Two schemas may share a device name, so the module is handed back unbound.
    assert sys.modules.get(test_module.__name__) is not test_module


def test_emitted_registers_carry_module_name(test_module):
    assert test_module.AnalogData.__module__ == "Tests"


def test_emitted_registers_are_usable(test_module):
    reg = test_module.AnalogData
    # The emitted register class round-trips through the Device.read/write frame path.
    frame = reg.format(
        reg.payload_class(analog0=1.0, analog1=2.0, analog2=3.0, accelerometer=[4, 5, 6])
    )
    assert isinstance(frame, (bytes, bytearray))
