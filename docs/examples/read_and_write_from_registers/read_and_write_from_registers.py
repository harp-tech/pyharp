from harp.device.core import (
    EnableFlag,
    OperationControl,
    OperationControlPayload,
    OperationMode,
    WhoAmI,
)
from harp.device.client import Device
from harp.serial import open_serial_device

SERIAL_PORT = "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)

with open_serial_device(Device, port=SERIAL_PORT) as device:
    # Read a scalar register.
    print("WhoAmI:", device.read(WhoAmI).parsed)

    # Read a structured register and inspect a field.
    control = device.read(OperationControl).parsed
    print("operation_mode before:", control.operation_mode)

    # Write the register, then read it back to confirm the change. A struct payload
    # is built whole, so every field is given a value.
    device.write(
        OperationControl,
        OperationControlPayload(
            operation_mode=OperationMode.ACTIVE,
            dump_registers=False,
            mute_replies=False,
            visual_indicators=EnableFlag.ENABLED,
            operation_led=EnableFlag.ENABLED,
            heartbeat=EnableFlag.DISABLED,
        ),
    )
    control = device.read(OperationControl).parsed
    print("operation_mode after:", control.operation_mode)
