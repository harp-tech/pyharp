# Reading a Whole Dataset Folder

A Harp acquisition is usually saved as a **de-multiplexed dataset folder**: one
binary file per register, named `<DeviceName>_<address>.bin`, next to the device's
`device.yml` schema. `harp.data.DatasetReader` reads that whole folder into pandas
DataFrames, driven by a [generated device](../../api/device.md) that describes how
to decode each register.

This is the recommended entry point when you have a recorded session on disk. To
decode a single loose `.bin` file instead, see
[Reading Data into a DataFrame](../read_data_to_dataframe/read_data_to_dataframe.md).

The quickest way in is `create_dataset_reader(folder)`: it finds the `device.yml`
inside the folder, builds the device for you, and returns a reader ready to go.
(If you already have a device class — e.g. from a pre-generated package — construct
`DatasetReader(Device, folder)` directly instead.) You then read a register by
class or by address, or read every register at once with `read_all()`. Timestamps
are detected automatically and placed on the `"Time"` index (float seconds, or an
absolute `DatetimeIndex` when you pass an `epoch`).

<!--codeinclude-->
```python
[](./read_dataset.py)
```
<!--/codeinclude-->
