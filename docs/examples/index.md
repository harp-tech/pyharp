# Examples

This section contains some examples to help you get started with `harp`.

Working from a device schema:

- [Generating a Device from a Schema](./create_device/create_device.md) - compile a `device.yml` into a typed device at runtime with `create_device`.

Talking to a device:

- [Getting Device Info](./get_info/get_info.md) - connect to a Harp device and read its information.
- [Read and Write from Registers](./read_and_write_from_registers/read_and_write_from_registers.md) - connect to a Harp device and read and write its registers.
- [Subscribing to Events](./subscribing_to_events/subscribing_to_events.md) - react to messages pushed by the device without polling.

Reading recorded data:

- [Reading Data into a DataFrame](./read_data_to_dataframe/read_data_to_dataframe.md) - load a register's binary data file into a pandas DataFrame with `harp.data`.
