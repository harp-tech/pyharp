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
- **The register namespace** — a `CoreRegisters` subclass **assigning** each of the
  device's own registers (`Encoder = Encoder`). Subclassing `CoreRegisters` merges in
  the common Harp registers.
- **The `Device` subclass** — names the namespace as its type parameter
  (`Device[ExampleRegisters]`) and sets **only** `__whoami__` (the expected identity)
  and `registers` (an instance of the namespace class).

The namespace class is the single source of truth: one declaration is both the
runtime register set and the static type, so the two can't drift.

Two details that look arbitrary but aren't. Members are **assignments**
(`Encoder = Encoder`), not `Encoder: type[Encoder]` annotations, because
`RegisterMap` introspects the class for real attribute values — an annotation-only
namespace resolves empty. Nothing is lost: a checker infers the assignment as
`type[Encoder]` either way. And because the right-hand side resolves through module
globals, register classes must live at module scope; `Encoder = Encoder` in a class
body nested inside a function raises `NameError`.

The namespace goes in as `Device`'s **type parameter** rather than a re-annotation of
`registers`. Re-declaring `registers: ClassVar[ExampleRegisters]` in the subclass
type-checks *worse*: a mutable attribute is invariant under override, so narrowing it
raises `reportIncompatibleVariableOverride` and every generated device would need a
suppression. Specializing a parameter isn't an override, so nothing needs suppressing
— and the checker verifies the assigned instance matches the parameter, making
`Device[ARegisters]` with `registers = BRegisters()` an error.

## What the base gives you

You never hand-build an address map. The base `Device`:

- resolves the namespace class into `device.registers` — reach a register by name
  (`device.registers.Encoder`), or use `device.registers.by_name` / `.by_address`;
- validates the device's `WhoAmI` against `__whoami__` on connect (`0x0` skips the check).

`CoreRegisters` contributes the common Harp registers through normal inheritance, so
on an address clash the most-derived register wins. A device that needs a different
common set may subclass `RegisterMap` directly instead.

Do **not** spread the common registers into your namespace, or override the base's
protocol methods (`read`, `write`, `subscribe`, lifecycle) — they are the base's job.
We may add a `@final` decorator to `Device` in the future to enforce this.

## For code generators

This is the contract a generator targets. Per device, emit:

1. Each register as a `RegisterBase` subclass (with its enums and payload classes), at
   module scope.
2. A namespace subclassing `CoreRegisters`, one `Name = Name` assignment per device
   register — **not** the common ones, which come from the base.
3. A `Device[<Namespace>]` subclass setting only `__whoami__` and
   `registers = <Namespace>()`. Emit the namespace as the **type parameter**, never
   as a re-annotation of `registers`.

Generators must **not** spread the common registers into the namespace, or override
any base `Device` method.

<!--codeinclude-->
```python
[](./static_device.py)
```
<!--/codeinclude-->
