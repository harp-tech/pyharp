from harp.device import Device, OperationControl, OperationControlPayload, OperationMode, WhoAmI
from harp.serial import open_serial_device

SERIAL_PORT = "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)

with open_serial_device(Device, port=SERIAL_PORT) as device:
    # Read a scalar register.
    print("WhoAmI:", device.read(WhoAmI).parsed)

    # Read a structured register and inspect a field.
    control = device.read(OperationControl).parsed
    print("operation_mode before:", control.operation_mode)

    # Write the register, then read it back to confirm the change.
    device.write(OperationControl, OperationControlPayload(operation_mode=OperationMode.ACTIVE))
    control = device.read(OperationControl).parsed
    print("operation_mode after:", control.operation_mode)
