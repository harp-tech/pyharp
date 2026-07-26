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

Downstream (often generated) packages add their registers and spread the core
`REGISTER_MAP`, and may set `__whoami__` for identity validation on connect:

```python
from harp.device import Device, REGISTER_MAP as _CORE_REGISTER_MAP

class MyDevice(Device):
    __whoami__ = 1216

REGISTER_MAP = {**_CORE_REGISTER_MAP, 32: DigitalInputState, ...}
```

A new transport is just an object implementing the `ITransport` protocol
(`open`/`write`/`read`/`close`).

## Generating a device from a `device.yml`

If you don't have a pre-generated device package, `create_device` builds a
`Device` from Harp `device.yml` text. Registers are reached by address through
`REGISTER_MAP`; field and enum names come from the yml verbatim.

```python
from pathlib import Path
from harp.device import create_device

Behavior = create_device(Path("device.yml").read_text())
reg = Behavior.REGISTER_MAP[44]
```

For a custom `interfaceType`, pass its converter via `converters=` (keyed by
`{InterfaceType}Converter` / `{MemberName}Converter`); an unresolved custom type
raises `UnknownConverterError`, or pass `strict=False` to decode it natively:

```python
create_device(yml_text, converters={"DataConverter": DataConverter()})
```

`parse_device_schema(yml_text)` is also public if you just want the parsed
schema model (registers, masks, and optional device identity) without a `Device`.
