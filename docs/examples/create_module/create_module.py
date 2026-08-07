from pathlib import Path

from harp.data import parse_to_dataframe
from harp.device import Device, create_module
from harp.serial import open_serial_device

SERIAL_PORT = "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)

# `create_module` compiles a Harp `device.yml` into a module of register classes at
# runtime — no code-generation step. This is the quickest way to work with a device
# when you don't have a pre-generated package for it: point it at the schema and you
# get the same shape a generated package has, registers at module level beside a
# `REGISTER_MAP`.
behavior = create_module(Path("device.yml").read_text())

print("WhoAmI:", behavior.WHO_AM_I)  # device identity, taken from the schema
AnalogData = behavior.AnalogData  # registers are reached by name...
assert behavior.REGISTER_MAP[44] is AnalogData  # ...or by address

# Registers are ordinary register classes, so they drive `read`/`write` on any
# `Device` over a transport. The schema carries no Python code, so there is no
# generated device class here: use `Device` itself.
with open_serial_device(Device, port=SERIAL_PORT) as device:
    print("AnalogData:", device.read(AnalogData).parsed)

# ...or use the same register classes to decode a recorded binary dump into a
# pandas DataFrame (see the "Reading Data into a DataFrame" example for more):
df = parse_to_dataframe(AnalogData, "Behavior_44.bin")
print(df.head())

# To have the identity checked on connect, subclass `Device` with the schema's
# WhoAmI — the same one-liner a generated package ships:
#
#   class Behavior(Device):
#       __whoami__ = behavior.WHO_AM_I


# --- Custom interface types --------------------------------------------------
# A register with a custom `interfaceType` needs a converter so its field decodes
# to the right Python type. Pass it via `converters=`, keyed by "<Name>Converter":
#
#   behavior = create_module(yml_text, converters={"DataConverter": DataConverter()})
#
# An unresolved custom type raises `UnknownConverterError`; pass `strict=False` to
# decode it natively instead. `exclude_private=True` (the default) drops registers
# marked `private` in the schema. If you only want the parsed schema model rather
# than a module, `parse_device_schema(yml_text)` returns that directly.
