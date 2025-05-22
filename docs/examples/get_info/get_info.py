from pyharp.protocol.device import Device

SERIAL_PORT = (
    "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)
)

# Open serial connection and save communication to a file
device = Device(SERIAL_PORT, "dump.bin")

# Display device's info on screen
device.info()

# Dump device's registers
reg_dump = device.dump_registers()
for reg_reply in reg_dump:
    print(reg_reply)
    print()

# Close connection
device.disconnect()
