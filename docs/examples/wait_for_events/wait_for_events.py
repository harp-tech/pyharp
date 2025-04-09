from pyharp import OperationMode
from pyharp.device import Device

SERIAL_PORT = (
    "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)
)

# Open serial connection and save communication to a file
device = Device(SERIAL_PORT, "dump.bin")

# Set device to Active Mode
device.set_mode(OperationMode.ACTIVE)
print("Setting mode to active.")

# Read device's events
while True:
    for msg in device.get_events():
        print(msg)
        print()
