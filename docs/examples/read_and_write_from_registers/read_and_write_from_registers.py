from harp.protocol import MessageType, PayloadType
from harp.protocol.messages import HarpMessage
from harp.serial.device import Device
from serial import SerialException

SERIAL_PORT = (
    "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)
)

# Open serial connection and save communication to a file
device = Device(SERIAL_PORT, "dump.bin")

# Check if the device is a Harp Behavior
if not device.WHO_AM_I == 1216:
    raise SerialException("This is not a Harp Behavior.")

# Read initial DI3 state
reply = device.send(HarpMessage.create(MessageType.READ, 32, PayloadType.U8))
print(reply.payload & 0x08)

# Turn DO0 on and read DI3 state after it
reply = device.send(HarpMessage.create(MessageType.READ, 34, PayloadType.U8, 0x400))
reply = device.send(HarpMessage.create(MessageType.READ, 32, PayloadType.U8))
print(reply.payload & 0x08)

# Turn DO0 off and read DI3 state again
reply = device.send(HarpMessage.create(MessageType.READ, 35, PayloadType.U8, 0x400))
reply = device.send(HarpMessage.create(MessageType.READ, 32, PayloadType.U8))
print(reply.payload & 0x08)

# Close connection
device.disconnect()
