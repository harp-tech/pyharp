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

A device is described by a module. Downstream, often generated, packages record the
device identity as `WHO_AM_I`, declare the register classes at module level, and expand
the core `REGISTER_MAP` beside them:

```python
from harp.device import REGISTER_MAP as _CORE_REGISTER_MAP

WHO_AM_I: int = 1216
REGISTER_MAP = {**_CORE_REGISTER_MAP, 32: DigitalInputState, ...}
```

This is the same structure `create_device_module` builds from a schema, so a device
reads the same way whether it was generated ahead of time or compiled at runtime. A
`WHO_AM_I` of `0` marks an unregistered device, used while a device is in development
or outside the official registry, and identity checks are skipped for it.

A device module names only the registers its schema declares, so `REGISTER_MAP` is the
device address space while the module namespace is what the device adds to it. The
common registers have a single definition, currently exported from `harp.device`, and
are not a device, so the core register set carries no `WHO_AM_I`.

`Device` itself holds no register collection. `read`, `write` and `subscribe` take a
register class, so the module is the only place registers need to live:

```python
from harp import behavior

# `device` is a Device opened over some transport (see harp-serial)
device.read(behavior.DigitalInputState)
```

Identity is not yet read from the module. To validate `WhoAmI` on connect, subclass
`Device` with the same value, which is what `open` checks against today:

```python
class MyDevice(Device):
    __whoami__ = 1216
```

A new transport is just an object implementing the `ITransport` protocol
(`open`/`write`/`read`/`close`).

## Generating registers from a `device.yml`

Without a pre-generated device package, `create_device_module` builds the same
structure at runtime from Harp `device.yml` text: register classes at module level, a
`REGISTER_MAP` beside them, and the identity declared by the schema as `WHO_AM_I`.
Identifiers match a generated package name for name: register, enum, and payload class
names come from the yml verbatim, payload fields are `snake_case`, and enum members are
`SCREAMING_SNAKE_CASE`.

```python
from pathlib import Path
from harp.device import create_device_module

behavior = create_device_module(Path("device.yml").read_bytes())
reg = behavior.AnalogData          # by name
reg = behavior.REGISTER_MAP[44]    # or by address
```

The module is not registered in `sys.modules`, so it has to be bound rather than
imported. Names come from the schema at runtime, so they don't autocomplete and
aren't statically checked. A generated package on disk gives both.

For a custom `interfaceType`, pass its converter via `converters=` (keyed by
`{InterfaceType}Converter` / `{MemberName}Converter`); an unresolved custom type
raises `UnknownConverterError`, or pass `strict=False` to decode it natively:

```python
create_device_module(yml_text, converters={"DataConverter": DataConverter()})
```

`parse_device_schema(yml_text)` is also public, returning the parsed schema model
without a module: registers, masks, and optional device identity.
