from harp.data import REFERENCE_EPOCH, create_dataset_reader
from harp.device import OperationControl

# A Harp acquisition is usually saved as a de-multiplexed dataset folder — one
# `.bin` file per register, named "<DeviceName>_<address>.bin", next to the
# device's `device.yml` schema:
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
reader = create_dataset_reader("session.harp")

# Read one register into a DataFrame — by register class (any register in the
# device's map, including the common ones like `OperationControl`)...
df = reader.read(OperationControl)

# ...or by address. Timestamps are auto-detected from the frames, and when present
# they become the DataFrame index, named "Time" (float seconds from device start).
df = reader.read(44)
print(df.head())

# Read every register that has a file on disk at once, keyed by register name.
everything = reader.read_all()
print(list(everything))

# Pass an epoch to turn the "Time" index into an absolute `DatetimeIndex` instead
# of float seconds. `REFERENCE_EPOCH` is time zero of the Harp clock (UTC).
absolute = reader.read(44, epoch=REFERENCE_EPOCH)
print(absolute.index[:3])

# --- Already have a device module? -------------------------------------------
# A pre-generated device package, or one you built yourself with `create_device_module`,
# can drive the reader directly — construct `DatasetReader(module, folder)`:
#
#   from harp.data import DatasetReader
#   from harp.device import create_device_module
#   from pathlib import Path
#
#   behavior = create_device_module((Path("session.harp") / "device.yml").read_bytes())
#   reader = DatasetReader(behavior, "session.harp")
