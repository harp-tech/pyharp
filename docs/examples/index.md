# Examples

This section contains examples for getting started with `harp`.

Working from a device schema:

- [Generating Registers from a Schema](./create_device_module/create_device_module.md) - compile a `device.yml` into a module of register classes at runtime with `create_device_module`.

Talking to a device:

- [Getting Device Info](./get_info/get_info.md) - connect to a Harp device and read its information.
- [Read and Write from Registers](./read_and_write_from_registers/read_and_write_from_registers.md) - connect to a Harp device and read and write its registers.
- [Subscribing to Events](./subscribing_to_events/subscribing_to_events.md) - react to messages pushed by the device without polling.

Reading recorded data:

- [Reading a Whole Dataset Folder](./read_dataset/read_dataset.md) - load an entire recorded session folder into pandas DataFrames with `DatasetReader`.
- [Reading Data into a DataFrame](./read_data_to_dataframe/read_data_to_dataframe.md) - decode the binary file of a single register into a pandas DataFrame.
