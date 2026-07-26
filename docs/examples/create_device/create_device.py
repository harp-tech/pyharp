from pathlib import Path

from harp.data import parse_to_dataframe
from harp.device import create_device
from harp.serial import open_serial_device

SERIAL_PORT = "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)

# `create_device` compiles a Harp `device.yml` into a typed `Device` subclass at
# runtime — no code-generation step. This is the quickest way to work with a device
# when you don't have a pre-generated package for it: point it at the schema and you
# get the device's registers (keyed by address) plus its identity.
Behavior = create_device(Path("device.yml").read_text())

print("WhoAmI:", Behavior.__whoami__)  # device identity, taken from the schema

# Registers are reached by name through `.registers` — the common Harp registers
# (like WhoAmI) plus the device's own. Address lookup goes through
# `Behavior.registers.by_address`.
AnalogData = Behavior.registers.AnalogData

# The generated device behaves like any other `Device` class. Talk to hardware over
# a transport — `read`/`write` take a register class:
with open_serial_device(Behavior, port=SERIAL_PORT) as device:
    print("AnalogData:", device.read(AnalogData).parsed)

# ...or use the same register classes to decode a recorded binary dump into a
# pandas DataFrame (see the "Reading Data into a DataFrame" example for more):
df = parse_to_dataframe(AnalogData, "Behavior_44.bin")
print(df.head())


# --- Custom interface types --------------------------------------------------
# A register with a custom `interfaceType` needs a converter so its field decodes
# to the right Python type. Pass it via `converters=`, keyed by "<Name>Converter":
#
#   Behavior = create_device(yml_text, converters={"DataConverter": DataConverter()})
#
# An unresolved custom type raises `UnknownConverterError`; pass `strict=False` to
# decode it natively instead. `exclude_private=True` (the default) drops registers
# marked `private` in the schema. If you only want the parsed schema model rather
# than a device, `parse_device_schema(yml_text)` returns that directly.
