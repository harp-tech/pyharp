# Subscribing to Events

This example demonstrates how to react to messages pushed by the device — e.g. unsolicited `Event` messages — without polling, using two subscription styles:

- `device.subscribe(register, handler)` — the handler receives a typed, parsed `ParsedHarpMessage` for a single register.
- `device.subscribe_all(handler)` — a catch-all handler that receives the raw `HarpMessage` for every register.

Handlers run on a dedicated event thread, so they never block `read()`/`write()`. Both methods return a `Subscription`; call `.unsubscribe()` (or use it as a context manager) to stop receiving events.

!!! warning
    Don't forget to change the `SERIAL_PORT` to the one that corresponds to your device! The `SERIAL_PORT` must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port.

<!--codeinclude-->
```python
[](./subscribing_to_events.py)
```
<!--/codeinclude-->
