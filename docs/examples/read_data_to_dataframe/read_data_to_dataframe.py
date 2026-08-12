from harp.data import parse_to_dataframe
from harp.device.core import OperationControl

# Parse a single register's binary dump into a pandas DataFrame — one row per
# frame, one column per field. The register class tells `parse_to_dataframe` how
# to decode each frame, so you get named columns (and decoded enums) for free.
df = parse_to_dataframe(OperationControl, "OperationControl.bin")
print(df.head())

# When the frames are timestamped (the default), the Harp time becomes the
# DataFrame index, named "Time" — float seconds from device start.
print(df.index.name, df.index[:3].to_list())

# `parse_to_dataframe` also accepts raw bytes or an open binary file object:
with open("OperationControl.bin", "rb") as f:
    df = parse_to_dataframe(OperationControl, f)

# To read a whole recorded session folder at once (many registers, driven by the
# device schema) use `harp.data.DatasetReader` — see the "Reading a Whole Dataset
# Folder" example.
