# harp-data

Load Harp register data into pandas DataFrames. This is the package that pulls
in `pandas` — [`harp-protocol`](../harp-protocol) stays numpy-only and exposes a
pandas-free `ColumnData` view that this package assembles into a DataFrame.

## Read a register from a file

`parse_to_dataframe` takes a register and a source (path, bytes, or open binary
file) and returns one row per frame:

```python
from harp.data import parse_to_dataframe
from my_device import AnalogData

df = parse_to_dataframe(AnalogData, "AnalogData.bin")
df = parse_to_dataframe(AnalogData, raw, timestamp=True, message_type=False, decode_enums=True)
```

Enum fields decode to `pd.Categorical` (`decode_enums=False` keeps raw codes).

## From an already-parsed payload

If you already have a batched payload (e.g. from `register.parse_bulk`), convert
it directly:

```python
from harp.data import payload_to_dataframe

_data, timestamps, _msg, payload = AnalogData.parse_bulk(raw)
df = payload_to_dataframe(payload)
```
