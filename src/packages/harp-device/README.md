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
who = device.read(WhoAmI).parsed  # -> np.uint16
device.write(OperationControl, payload)  # write a register
```

## Extending for a specific device

Downstream (often generated) packages declare their registers as attributes on a
`CoreRegisters` subclass, name that class as `Device`'s type parameter, and assign an
instance of it to `registers`. They may set `__whoami__` for identity validation on
connect. Only these two attributes are meant to be set — the base owns the protocol
methods:

```python
from harp.device import CoreRegisters, Device


class MyRegisters(CoreRegisters):
    DigitalInputState = DigitalInputState
    ...


class MyDevice(Device[MyRegisters]):
    __whoami__ = 1216
    registers = MyRegisters()
```

That single declaration is both the runtime register set — `RegisterMap`
introspects the class to build its name and address maps — and the static type, so
`MyDevice.registers.DigitalInputState` autocompletes and `read`/`write` infer the
payload type. Registers are also reachable through the `MyDevice.registers.by_name`
and `.by_address` maps. Subclassing `CoreRegisters` is what merges in the common Harp
registers; a device needing a different common set may subclass `RegisterMap`
directly. See the [device examples](https://harp-tech.org/pyharp/examples/).

A new transport is just an object implementing the `ITransport` protocol
(`open`/`write`/`read`/`close`).

## Generating a device from a `device.yml`

If you don't have a pre-generated device package, `create_device` builds a
`Device` from Harp `device.yml` text. Registers are reached by name through
`device.registers`; field and enum names come from the yml verbatim.

```python
from pathlib import Path
from harp.device import create_device

Behavior = create_device(Path("device.yml").read_text())
reg = Behavior.registers.AnalogData  # by name (or Behavior.registers.by_address[44])
```

For a custom `interfaceType`, pass its converter via `converters=` (keyed by
`{InterfaceType}Converter` / `{MemberName}Converter`); an unresolved custom type
raises `UnknownConverterError`, or pass `strict=False` to decode it natively:

```python
create_device(yml_text, converters={"DataConverter": DataConverter()})
```

`parse_device_schema(yml_text)` is also public if you just want the parsed
schema model (registers, masks, and optional device identity) without a `Device`.
