# harp-data

Load Harp register data into pandas DataFrames. This is the package that pulls in `pandas`. [`harp-protocol`](../harp-protocol) stays numpy-only and exposes a pandas-free `ColumnData` view that this package assembles into a DataFrame.

There are two ways in, depending on what is on disk:

- a whole **dataset folder** holding many registers, read with `DatasetReader`
- a single **register file** or buffer, read with `parse_to_dataframe`

## Read a whole dataset folder

A Harp acquisition is usually saved as a de-multiplexed folder, one binary file per register, named `<DeviceName>_<address>.bin`, alongside the `device.yml` schema for the device:

```text
📦 session.harp
 ┣ 📜 Behavior_0.bin
 ┣ 📜 Behavior_44.bin
 ┣ ...
 ┗ 📜 device.yml
```

Reading is based on a [device module](../harp-device) that describes how to decode each register. `create_dataset_reader` supplies one automatically. It finds the `device.yml` in the folder, builds the module, and returns a ready-to-use reader:

```python
from harp import data

reader = data.create_dataset_reader("session.harp")
behavior = reader.device_module
df = reader.read(behavior.AnalogData)  # by register class
df = reader.read(44)                   # by address
```

Given a device module already in hand, either a pre-generated package or one built with `create_device_module`, pass it to `DatasetReader` directly:

```python
from harp import data
from harp.device import behavior

reader = data.DatasetReader(behavior, "session.harp")
df = reader.read(behavior.AnalogData)
```

Timestamps are auto-detected per register and placed on the DataFrame index named `"Time"`: float seconds by default, or an absolute `DatetimeIndex` when `epoch=REFERENCE_EPOCH` is passed. Multi-chunk registers logged as `<DeviceName>_<address>_<suffix>.bin` are concatenated in filename order; pass a `resolver` to support an alternative on-disk layout.

The `<DeviceName>` prefix comes from the `DEVICE_NAME` declared by the device module. Pass `name=` to override it, or to supply one when the module declares an empty name.

When the folder carries a `device.yml` and the module declares an identity, their `whoAmI` values are checked against each other. Reusing a module across sessions and reaching the wrong folder then fails on construction rather than decoding the files against the wrong register map. Pass `validate=False` to turn off every check the reader performs, so a folder whose `device.yml` is damaged can be read with a module obtained elsewhere.

## Read a single register file

`parse_to_dataframe` takes a register and a source, either a path, bytes, or an open binary file, and returns one row per frame:

```python
from harp import data
from my_device import AnalogData

df = data.parse_to_dataframe(AnalogData, "AnalogData.bin")
df = data.parse_to_dataframe(
    AnalogData, raw, timestamp=True, message_type=False, decode_enums=True
)
```

With `timestamp=True`, the default, the Harp time becomes the DataFrame index named `"Time"`, as float seconds, or an absolute `DatetimeIndex` when `epoch=REFERENCE_EPOCH` is also passed. Enum fields decode to `pd.Categorical`, and `decode_enums=False` keeps raw codes.

## From an already-parsed payload

Given a batched payload already in hand, for example from `register.parse_bulk`, convert it directly:

```python
from harp import data

_data, timestamps, _msg, payload = AnalogData.parse_bulk(raw)
df = data.payload_to_dataframe(payload)
```

## Write data back out

`to_file` and `to_buffer` are the inverse of the readers, encoding values as Harp frames. Useful for round-tripping data or generating test corpora:

```python
from harp import data

data.to_file(AnalogData, values, "AnalogData.bin", timestamps=seconds)
```
