# harp-device

The transport-agnostic device layer for the Harp protocol: the common Harp
registers and a `Device` base that handles framing, request/reply and register
access. It depends only on [`harp-protocol`](../harp-protocol) — no transport
dependencies. Pair it with a transport (e.g. [`harp-serial`](../harp-serial)).

## Read/write registers

A `Device` is driven over a transport; `read`/`write` take a register class:

```python
from harp.device import Device, WhoAmI, OperationControl

# `device` is a Device opened over some transport (see harp-serial)
who = device.read(WhoAmI).parsed          # -> np.uint16
device.write(OperationControl, payload)   # write a register
```

## Extending for a specific device

A device's registers live in its module. Downstream (often generated) packages
declare them at module level and spread the core `REGISTER_MAP` beside them, and may
subclass `Device` to set `__whoami__` for identity validation on connect:

```python
from harp.device import Device, REGISTER_MAP as _CORE_REGISTER_MAP

class MyDevice(Device):
    __whoami__ = 1216

REGISTER_MAP = {**_CORE_REGISTER_MAP, 32: DigitalInputState, ...}
```

`Device` itself holds no register collection: `read`, `write` and `subscribe` take a
register class, so the module namespace is the only place registers need to live.

A new transport is just an object implementing the `ITransport` protocol
(`open`/`write`/`read`/`close`).

## Generating registers from a `device.yml`

If you don't have a pre-generated device package, `create_module` builds the same
shape at runtime from Harp `device.yml` text: register classes at module level, a
`REGISTER_MAP` beside them, and the schema's identity as `WHO_AM_I`. Field and enum
names come from the yml verbatim.

```python
from pathlib import Path
from harp.device import create_module

behavior = create_module(Path("device.yml").read_text())
reg = behavior.AnalogData          # by name
reg = behavior.REGISTER_MAP[44]    # or by address
```

The module is not registered in `sys.modules`, so bind it yourself rather than
`import`-ing it; names come from the schema at runtime, so they don't autocomplete
and aren't statically checked, which is what a generated package on disk buys you.

For a custom `interfaceType`, pass its converter via `converters=` (keyed by
`{InterfaceType}Converter` / `{MemberName}Converter`); an unresolved custom type
raises `UnknownConverterError`, or pass `strict=False` to decode it natively:

```python
create_module(yml_text, converters={"DataConverter": DataConverter()})
```

`parse_device_schema(yml_text)` is also public if you just want the parsed
schema model (registers, masks, and optional device identity) without a module.
