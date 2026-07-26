# Examples

This section contains some examples to help you get started with `harp`.

Defining a device:

- [Defining a Device Statically](./static_device/static_device.md) - write a device as plain, typed Python classes (the shape code generators emit).
- [Generating a Device from a Schema](./create_device/create_device.md) - compile a `device.yml` into a typed device at runtime with `create_device`.

Talking to a device:

- [Getting Device Info](./get_info/get_info.md) - connect to a Harp device and read its information.
- [Read and Write from Registers](./read_and_write_from_registers/read_and_write_from_registers.md) - connect to a Harp device and read and write its registers.
- [Subscribing to Events](./subscribing_to_events/subscribing_to_events.md) - react to messages pushed by the device without polling.

Reading recorded data:

- [Reading a Whole Dataset Folder](./read_dataset/read_dataset.md) - load an entire recorded session folder into pandas DataFrames with `DatasetReader`.
- [Reading Data into a DataFrame](./read_data_to_dataframe/read_data_to_dataframe.md) - decode a single register's binary file into a pandas DataFrame.
