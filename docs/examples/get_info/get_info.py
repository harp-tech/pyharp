from harp.device import Device, WhoAmI
from harp.serial import open_serial_device

SERIAL_PORT = "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)

# Open a serial connection to the device (closed automatically on exit).
with open_serial_device(Device, port=SERIAL_PORT) as device:
    # Identify the device.
    print("WhoAmI:", device.read(WhoAmI).parsed)

    # Dump every register the device exposes. `device.registers` is name-addressable
    # (device.registers.WhoAmI); `.by_address` gives the address -> register map.
    for address, register in sorted(device.registers.by_address.items()):
        reply = device.read(register)
        print(f"{register.__name__:24s} (addr {address:2d}) = {reply.parsed}")
