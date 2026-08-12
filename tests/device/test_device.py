import types

from harp.device.client import Device


class _NullTransport:
    def open(self) -> None: ...

    def close(self) -> None: ...

    def write(self, data: bytes) -> None: ...

    def read(self) -> bytes:
        return b""


def _module(name: str, **attrs: object) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


def test_whoami_of_zero_skips_the_check():
    # 0 marks an unregistered device, so opening must not read WhoAmI at all.
    device = Device(_NullTransport(), _module("Unregistered", WHO_AM_I=0, REGISTER_MAP={}))
    with device:
        assert device.module.WHO_AM_I == 0


def test_module_is_returned_by_the_property():
    module = _module("Behavior", WHO_AM_I=0, REGISTER_MAP={})
    assert Device(_NullTransport(), module).module is module
    assert Device(_NullTransport()).module is None
