from harp.device import (
    Device,
    OperationControl,
    OperationControlPayload,
    OperationMode,
    TimestampSeconds,
)
from harp.protocol import HarpMessage, ParsedHarpMessage
from harp.serial import open_serial_device

SERIAL_PORT = "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)


def print_timestamp(msg: ParsedHarpMessage[float]) -> None:
    print(f"[timestamp] {msg.timestamp:.6f}  {msg.parsed}")


def print_any_event(msg: HarpMessage) -> None:
    register = Device.registers.by_address.get(msg.address)
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
            heartbeat=True,
            mute_replies=False,
            operation_led=True,
            visual_indicators=True,
        ),
    )

    input("Listening for events. Press Enter to stop.\n")
    timestamp_subscription.unsubscribe()
