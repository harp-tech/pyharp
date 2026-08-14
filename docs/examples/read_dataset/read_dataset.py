from harp import data
from harp.device import core

# A Harp acquisition is usually saved as a de-multiplexed dataset folder, one
# `.bin` file per register, named "<DeviceName>_<address>.bin", next to the
# `device.yml` schema for the device:
#
#   📦 session.harp
#    ┣ 📜 Behavior_0.bin
#    ┣ 📜 Behavior_44.bin
#    ┣ ...
#    ┗ 📜 device.yml
#
# `create_dataset_reader` does the right thing: it finds `device.yml` inside the
# folder, builds the module of register classes that knows how to decode each
# register, and hands back a reader ready to go.
reader = data.create_dataset_reader("session.harp")

# Read one register into a DataFrame by register class, which covers any register
# in the device map, including common ones such as `OperationControl`.
df = reader.read(core.OperationControl)

# A register can also be read by address. Timestamps are auto-detected from the
# frames, and when present they become the DataFrame index, named "Time", holding
# float seconds from device start.
df = reader.read(44)
print(df.head())

# Read every register that has a file on disk at once, keyed by register name.
everything = reader.read_all()
print(list(everything))

# Pass an epoch to turn the "Time" index into an absolute `DatetimeIndex` instead
# of float seconds. `REFERENCE_EPOCH` is time zero of the Harp clock in UTC.
absolute = reader.read(44, epoch=data.REFERENCE_EPOCH)
print(absolute.index[:3])

# --- Working from a device module already in hand ----------------------------
# A pre-generated device package, or one built with `create_device_module`,
# can be passed to the reader directly as `DatasetReader(module, folder)`:
#
#   from pathlib import Path
#
#   from harp import data
#   from harp.device import schema
#
#   behavior = schema.create_device_module((Path("session.harp") / "device.yml").read_bytes())
#   reader = data.DatasetReader(behavior, "session.harp")
