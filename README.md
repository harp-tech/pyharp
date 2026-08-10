<p align="center">
  <img src="https://raw.githubusercontent.com/harp-tech/pyharp/c0c8c23cc1a965c41834a106fe686be76c2f0520/docs/assets/logo.svg" alt="Harp logo" width="400">
</p>

# harp

This project includes four main packages:

 - **harp-protocol**: Provides the core protocol definitions and utilities for the Harp protocol.
   See [Protocol API Documentation](https://harp-tech.org/pyharp/api/protocol) for details.

 - **harp-serial**: Implements serial communication functionalities for generic Harp devices.
   See [Serial API Documentation](https://harp-tech.org/pyharp/api/serial) for more information.

 - **harp-device**: Implements the transport-agnostic `Device` interface, the common register map, and the shared registers and enums.
   See [Device API Documentation](https://harp-tech.org/pyharp/api/device) for details.

 - **harp-data**: Parses register binary dumps into pandas DataFrames.
   See [Data API Documentation](https://harp-tech.org/pyharp/api/data) for more information.

## Installation

All packages are published to PyPI. The `harp` package is a metadata package with no code of
its own — it just depends on the four packages above, so it's the easiest way to get everything:

```sh
pip install harp
```

```sh
uv add harp
```

If you only need part of the stack (e.g. you're parsing offline data dumps and don't need serial
I/O), install just the packages you need — each one only pulls in what it actually depends on:

| Package | Provides | Depends on |
| --- | --- | --- |
| `harp-protocol` | Core protocol types: registers, messages, payload parsing | — |
| `harp-device` | Transport-agnostic `Device` class, common register map | `harp-protocol` |
| `harp-serial` | Serial (COM/tty) transport for `Device` | `harp-protocol`, `harp-device` |
| `harp-data` | Parse register binary dumps into pandas DataFrames | `harp-protocol` |

```sh
pip install harp-protocol
pip install harp-device
pip install harp-serial
pip install harp-data
```

`harp-benchmarks` (under `src/packages/`) is internal-only and is never published to PyPI.

## Quickstart

Have only a device's `device.yml`? `create_device` compiles it into a typed
`Device` at runtime — no code-generation step — giving you the device's registers
(keyed by address) and its identity:

```python
from pathlib import Path
from harp.device import create_device

Behavior = create_device(Path("device.yml").read_text())
Behavior.__whoami__            # device identity from the schema
AnalogData = Behavior.REGISTER_MAP[44]   # registers are reached by address
```

The generated device works like any other. **Talk to hardware** over a serial
transport — `read`/`write` take a register class:

```python
from harp.serial import open_serial_device

# Use "COMx" on Windows, "/dev/ttyUSBx" on Linux.
with open_serial_device(Behavior, port="/dev/ttyUSB0") as device:
    print(device.read(AnalogData).parsed)
```

...or use the same register classes to **decode recorded data** into a pandas
DataFrame:

```python
from harp.data import parse_to_dataframe

df = parse_to_dataframe(AnalogData, "Behavior_44.bin")
```

See the [Examples](https://harp-tech.org/pyharp/examples/) for full walkthroughs,
including reading device info, subscribing to events, and working with custom
interface-type converters.

## Contributing

harp is a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/): every package under
`src/packages/` is its own distribution, plus the root `harp` metadata package. Contributions are
welcome — please open an issue or PR.

Clone the repo and install everything (all workspace packages, editable, plus test/lint tooling)
with the `dev` dependency group:

```sh
uv sync --group dev
```

Before opening a PR, run the same checks CI runs:

```sh
uv run ruff format --check   # formatting
uv run ruff check            # lint
uv run ty check              # type checking
uv run codespell             # spelling
uv run pytest --cov harp     # tests
```

Adding a new package? Drop it under `src/packages/<name>/` with its own `pyproject.toml`, add it
to `[tool.uv.sources]` in the root `pyproject.toml`, and (if it should ship as part of `harp`) add
it to the root package's `dependencies` too.

## Building the documentation

Install the docs dependency group and run mkdocs through uv:

```sh
uv sync --group docs --group dev
uv run mkdocs serve   # live-reloading local preview
uv run mkdocs build   # static site in ./site
```
