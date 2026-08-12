import numpy as np
from harp.device.core import (
    EnableFlag,
    OperationControl,
    OperationControlPayload,
    OperationMode,
    REGISTER_MAP,
    TimestampSeconds,
)
from harp.device.client import Device
from harp.protocol import HarpMessage, ParsedHarpMessage
from harp.serial import open_serial_device

SERIAL_PORT = "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)


def print_timestamp(msg: ParsedHarpMessage[np.uint32]) -> None:
    print(f"[timestamp] {msg.timestamp:.6f}  {msg.parsed}")


def print_any_event(msg: HarpMessage) -> None:
    register = REGISTER_MAP.get(msg.address, None)
    value = register.parse(msg) if register is not None else msg.payload.hex()
    print(f"[{msg.address}] {msg.timestamp:.6f}  {msg.message_type.name:<5s}  {value}")


with open_serial_device(Device, port=SERIAL_PORT) as device:
    # Subscribe to a single, typed register: the handler receives a parsed payload.
    timestamp_subscription = device.subscribe(TimestampSeconds, print_timestamp)

    # Subscribe to every register at once: the handler receives the raw message.
    device.subscribe_all(print_any_event)

    device.write(
        OperationControl,
        OperationControlPayload(
            operation_mode=OperationMode.ACTIVE,
            dump_registers=True,
            heartbeat=EnableFlag.ENABLED,
            mute_replies=False,
            operation_led=EnableFlag.ENABLED,
            visual_indicators=EnableFlag.ENABLED,
        ),
    )

    input("Listening for events. Press Enter to stop.\n")
    timestamp_subscription.unsubscribe()
