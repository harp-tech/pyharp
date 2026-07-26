# Defining a Device Statically

There are two ways to get a [`Device`](../../api/device.md): compile one at runtime
from a `device.yml` with [`create_device`](../create_device/create_device.md), or
define one **statically** as plain Python classes. This article covers the static
form — what you write by hand for a distributable, fully typed device package, and
exactly the shape a code generator emits from a `device.yml`.

Prefer the static form when you want an importable device with real register classes,
editor autocomplete, and static type checking (`read`/`write` inferring payload
types). Prefer `create_device` when you only have a schema in hand and don't need a
published package.

## The pieces

A static device is four kinds of declaration:

- **Register classes** — each a `RegisterBase` subclass carrying its `address`.
  Scalars can use the `Register<Type>` shortcuts (e.g. `RegisterU16`); structured
  registers set `payload_type` and point at a payload class.
- **Enums and payload classes** — `IntEnum` / `IntFlag` for enum and mask fields, and
  `StructPayload` / `AnonymousPayload` subclasses describing multi-field payloads.
- **The `Device` subclass** — sets **only** `__whoami__` (the expected identity) and
  `__REGISTERS__` (a tuple of the device's **own** registers). The common Harp
  registers are merged in and `device.registers` is derived automatically.
- **A typed facade** (optional but recommended) — under `TYPE_CHECKING`, a
  `CoreRegisters` subclass declaring `Name: type[Name]` for each register, so
  `device.registers.<Name>` autocompletes and types precisely.

## What the base gives you

You never hand-build an address map. The base `Device`:

- merges the common Harp registers with `__REGISTERS__` (device wins on an address clash);
- derives `device.registers` — reach a register by name (`device.registers.Encoder`),
  or use `device.registers.by_name` / `.by_address`;
- validates the device's `WhoAmI` against `__whoami__` on connect (`0x0` skips the check).

Do **not** declare a `REGISTER_MAP`, spread the common registers into `__REGISTERS__`,
or override the base's protocol methods (`read`, `write`, `subscribe`, lifecycle) —
they are the base's job.

!!! note "The typed facade"
    The facade under `TYPE_CHECKING` narrows the base's `registers` attribute, which
    the type checker would otherwise flag as an incompatible override — hence the one
    `# pyright: ignore[reportIncompatibleVariableOverride]`. It carries no runtime
    values; the actual namespace is always built from `__REGISTERS__` by the base.
    Skip the facade and `device.registers.<Name>` still works, typed as the generic
    `type[RegisterBase]` (no per-register autocomplete).

## For code generators

This is the contract a generator targets. Per device, emit:

1. Each register as a `RegisterBase` subclass (with its enums and payload classes).
2. A `Device` subclass setting only `__whoami__` and `__REGISTERS__` (the device's own
   registers — **not** the common ones).
3. A `TYPE_CHECKING` facade subclassing `CoreRegisters`, one `Name: type[Name]` per
   device register, plus `registers: ClassVar[<Facade>]`.

Generators must **not** emit a `REGISTER_MAP`, spread the common registers into
`__REGISTERS__`, or override any base `Device` method.

<!--codeinclude-->
```python
[](./static_device.py)
```
<!--/codeinclude-->
