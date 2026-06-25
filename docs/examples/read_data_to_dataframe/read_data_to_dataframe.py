from harp.data import read_dataframe
from harp.device import OperationControl

# Parse a register's binary dump into a pandas DataFrame — one row per frame,
# one column per field, plus a leading "timestamp" column.
df = read_dataframe(OperationControl, "OperationControl.bin", timestamp=True)
print(df.head())

# `read_dataframe` also accepts raw bytes or an open binary file object:
with open("OperationControl.bin", "rb") as f:
    df = read_dataframe(OperationControl, f)
