# pyharp

This project includes four main packages:

 - **harp-protocol**: Provides the core protocol definitions and utilities for the Harp protocol.
   See [Protocol API Documentation](https://harp-tech.org/pyharp/api/protocol) for details.

 - **harp-serial**: Implements serial communication functionalities for generic Harp devices.
   See [Serial API Documentation](https://harp-tech.org/pyharp/api/serial) for more information.

 - **harp-device**: Implements the transport-agnostic `Device` interface, the common register map, and the shared registers and enums.
   See [Device API Documentation](https://harp-tech.org/pyharp/api/device) for details.

 - **harp-data**: Parses register binary dumps into pandas DataFrames.
   See [Data API Documentation](https://harp-tech.org/pyharp/api/data) for more information.

## Building the documentation

Install the docs dependency group and run mkdocs through uv:

```sh
uv sync --group docs --group dev
uv run mkdocs serve   # live-reloading local preview
uv run mkdocs build   # static site in ./site
```
