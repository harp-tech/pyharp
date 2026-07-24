# harp-serial

Serial transport for [`harp-device`](../harp-device). Provides `SerialTransport`
and the `open_serial_device` factory, which pairs a `Device` class with a serial
port. This is the package that pulls in `pyserial`.

## Usage

Like the builtin `open`, the returned device is connected and ready; use it in a
`with` block for guaranteed cleanup:

```python
from harp.device import Device, WhoAmI
from harp.serial import open_serial_device

with open_serial_device(Device, port="COM3", baudrate=1_000_000) as dev:
    print(dev.read(WhoAmI).parsed)
```

Pass any `Device` subclass (e.g. a generated device class) instead of the base
`Device` to talk to a specific device.
