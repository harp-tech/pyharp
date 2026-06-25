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
