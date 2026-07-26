# Generating a Device from a Schema

This example demonstrates how to turn a Harp `device.yml` into a typed
[`Device`](../../api/device.md) at runtime with `create_device`, without a
code-generation step. This is the quickest way to get started when you have only a
device's schema and no pre-generated package for it.

The compiled device exposes its registers by name through `device.registers`
(e.g. `Behavior.registers.AnalogData`, or by address with `Behavior.registers[44]`)
and carries the device's `__whoami__` identity. From there it works exactly like a
pre-generated device class — drive it over a transport to talk to hardware, or use
its register classes to decode recorded data.

## When to use runtime generation

`create_device` trades statically generated device packages for schema-driven
convenience. It's worth understanding what that buys you and what it costs.

**You gain:**

- **No build step.** A `device.yml` — even one you just pulled off a device —
  becomes a working device in a single call. There's nothing to generate, install,
  or keep in sync with the schema.
- **Coverage for any device.** You don't need a published package for the device;
  unreleased, custom, or one-off schemas work immediately.
- **The schema stays the single source of truth.** Register, field, and enum names
  come straight from the `device.yml`, verbatim.

**You give up:**

- **Static register types.** A runtime device still exposes its registers by name
  (`device.registers.AnalogData`), but because the class is built at runtime the
  editor can't autocomplete those names or check them — you get a generic
  `type[RegisterBase]`, not the specific register type. A statically generated device
  declares its registers, so `device.registers.AnalogData` autocompletes and
  `read`/`write` infer the payload type.
- **Generator naming conventions.** Identifiers are kept verbatim from the yml
  (`AnalogInput0`, `DIO0`) rather than the C# generator's snake_case fields and
  `UPPER_SNAKE` enum members, so code written against a generated package won't line
  up name-for-name.
- **Turn-key custom types.** A custom `interfaceType` must be injected yourself via
  `converters=` (see below), whereas a generated package ships its own converters.

For shipped, widely-used devices a pre-generated package from the
[Harp C# generator](https://github.com/harp-tech/generators) remains the
authoritative choice — better editor support and static typing. Reach for
`create_device` when you want to go from a schema to working code with no
generation step.

!!! warning
    Don't forget to change the `SERIAL_PORT` to the one that corresponds to your device! The `SERIAL_PORT` must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port.

<!--codeinclude-->
```python
[](./create_device.py)
```
<!--/codeinclude-->
