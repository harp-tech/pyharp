# harp-data

Load Harp register data into pandas DataFrames. This is the package that pulls
in `pandas` — [`harp-protocol`](../harp-protocol) stays numpy-only and exposes a
pandas-free `ColumnData` view that this package assembles into a DataFrame.

There are two ways in, depending on what you have on disk:

- a whole **dataset folder** (many registers) → `DatasetReader`
- a single **register file** or buffer → `parse_to_dataframe`

## Read a whole dataset folder

A Harp acquisition is usually saved as a de-multiplexed folder — one binary file
per register, named `<DeviceName>_<address>.bin`, alongside the device's
`device.yml` schema:

```text
📦 session.harp
 ┣ 📜 Behavior_0.bin
 ┣ 📜 Behavior_44.bin
 ┣ ...
 ┗ 📜 device.yml
```

Reading is driven by a generated
[`harp.device.client.Device`](../harp-device) that describes how to decode each register.
`create_dataset_reader` does that for you — it finds the `device.yml` in the folder,
builds the device, and returns a ready-to-use reader:

```python
from harp.data import create_dataset_reader

reader = create_dataset_reader("session.harp")
df  = reader.read(AnalogData)     # by register class
df  = reader.read(44)             # by address
everything = reader.read_all()    # {register_name: DataFrame}
```

Already have a device module (e.g. a pre-generated package, or one built with
`create_device_module`)? Drive `DatasetReader` with it directly:

```python
from pathlib import Path
from harp.data import DatasetReader
from harp.device.schema import create_device_module

behavior = create_device_module((Path("session.harp") / "device.yml").read_bytes())
reader = DatasetReader(behavior, "session.harp")
```

Timestamps are auto-detected per register and placed on the DataFrame index
(named `"Time"`): float seconds by default, or an absolute `DatetimeIndex` when
you pass `epoch=REFERENCE_EPOCH`. Multi-chunk registers logged as
`<DeviceName>_<address>_<suffix>.bin` are concatenated in filename order; pass a
`resolver` to support an alternative on-disk layout, or `name=` to override the
file prefix.

## Read a single register file

`parse_to_dataframe` takes a register and a source (path, bytes, or open binary
file) and returns one row per frame:

```python
from harp.data import parse_to_dataframe
from my_device import AnalogData

df = parse_to_dataframe(AnalogData, "AnalogData.bin")
df = parse_to_dataframe(AnalogData, raw, timestamp=True, message_type=False, decode_enums=True)
```

With `timestamp=True` (the default) the Harp time becomes the DataFrame index,
named `"Time"` — float seconds, or an absolute `DatetimeIndex` when you also pass
`epoch=REFERENCE_EPOCH`. Enum fields decode to `pd.Categorical`
(`decode_enums=False` keeps raw codes).

## From an already-parsed payload

If you already have a batched payload (e.g. from `register.parse_bulk`), convert
it directly:

```python
from harp.data import payload_to_dataframe

_data, timestamps, _msg, payload = AnalogData.parse_bulk(raw)
df = payload_to_dataframe(payload)
```

## Align a non-Harp device to the Harp clock

Devices outside the Harp bus keep their own clock. Some clock emitters mirror the
[Synchronization Clock](https://harp-tech.org/protocol/SynchronizationClock.html)
on a digital output at a much lower baud rate (typically 1 kbps rather than
100 kbps) so that those devices can record it and be aligned post-hoc.
`harp.data.synchronization` turns such a recording back into a table of anchors,
keyed on whichever axis the device timestamps its own data on — the sample the
packet was received at, or its local time in seconds — against the Harp second
(`"Time"`) that packet carries:

```python
import numpy as np
from harp.data.synchronization import decode_clock_from_samples

clock = decode_clock_from_samples(sync_line, sample_rate=30_000.0)  # Sample -> Time
harp_times = np.interp(spike_samples, clock.index, clock["Time"])

# event-based systems report transitions instead, so anchors carry local seconds
clock = decode_clock_from_transitions(edge_times, edge_states)      # LocalTime -> Time
harp_times = np.interp(spike_times, clock.index, clock["Time"])
```

Packets that fail their start/stop bit check, or whose seconds do not add up
against the local clock, are dropped — a glitched packet costs one anchor, not the
alignment around it. By default anchors sit on the last transmitted bit of each
packet, mirroring the protocol's synchronization event; pass
`anchor="first_edge"` for emitters that align the whole second to the start of the
transmission instead.

## Write data back out

`to_file` / `to_buffer` are the inverse of the readers — encode values as Harp
frames. Handy for round-tripping data or generating test corpora:

```python
from harp.data import to_file

to_file(AnalogData, values, "AnalogData.bin", timestamps=seconds)
```
