# Generating Registers from a Schema

This example demonstrates how to turn a Harp `device.yml` into a module of register
classes at runtime with `create_device_module`, without a code-generation step. This is the
quickest way to get started when you have only a device's schema and no
pre-generated package for it.

A generated device package is a module: register classes at module level, with a
`REGISTER_MAP` beside them keyed by address. `create_device_module` builds that same shape
from a schema, so registers are reached the same way either way — by name
(`behavior.AnalogData`) or by address (`behavior.REGISTER_MAP[44]`). From there they
work exactly like a pre-generated package's: drive them over a transport with
[`Device`](../../api/device.md) to talk to hardware, or use them to decode recorded
data.

## When to use runtime generation

`create_device_module` trades statically generated device packages for schema-driven
convenience. It's worth understanding what that buys you and what it costs.

**You gain:**

- **No build step.** A `device.yml` — even one you just pulled off a device —
  becomes a working module in a single call. There's nothing to generate, install,
  or keep in sync with the schema.
- **Coverage for any device.** You don't need a published package for the device;
  unreleased, custom, or one-off schemas work immediately.
- **The schema stays the single source of truth.** Registers, fields, and enums come
  straight from the `device.yml`, under the same naming convention a generated
  package uses — so code written against either lines up name for name.

**You give up:**

- **Static typing and autocomplete.** The names exist only once the module is built,
  so an editor can't offer them and a type checker can't verify them. A generated
  package is a real module on disk, so both work. The module also isn't in
  `sys.modules`, so you bind it yourself rather than `import`-ing it.
- **Turn-key custom types.** A custom `interfaceType` must be injected yourself via
  `converters=` (see below), whereas a generated package ships its own converters.

For shipped, widely-used devices a pre-generated package from the
[Harp C# generator](https://github.com/harp-tech/generators) remains the
authoritative choice — better editor support and static typing. Reach for
`create_device_module` when you want to go from a schema to working code with no
generation step.

!!! warning
    Don't forget to change the `SERIAL_PORT` to the one that corresponds to your device! The `SERIAL_PORT` must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port.

<!--codeinclude-->
```python
[](./create_device_module.py)
```
<!--/codeinclude-->
