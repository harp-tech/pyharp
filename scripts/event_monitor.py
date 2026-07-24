"""Example: subscribe to all events from a Harp device and print them.

Connects to a device on COM3, registers a single catch-all handler for *every*
event, and prints each one to the console until you press Ctrl+C.

Run with:
    uv run python scripts/event_monitor.py
"""

import time

from harp.device import (
    REGISTER_MAP,
    Device,
    OperationControl,
    OperationControlPayload,
    OperationMode,
    TimestampSeconds,
)
from harp.device.rx import observe
from harp.protocol import HarpMessage, MessageType
from harp.serial import open_serial_device
from reactivex import operators as ops

PORT = "COM3"


def print_event(msg: HarpMessage) -> None:
    if msg.address == 44:  # too damn noisy
        return
    register = REGISTER_MAP.get(msg.address, None)
    if register is not None:
        value = register.parse(msg)
    else:
        value = msg.payload.hex()
    print(f"NonRx: {msg.timestamp:.6f}  {msg.address}  {msg.message_type.name:<5s}  {value}")


if __name__ == "__main__":
    with open_serial_device(Device, port=PORT) as dev:
        dev.write(
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
        disposable = (
            observe(dev, TimestampSeconds)
            .pipe(
                ops.filter(lambda msg: msg.message_type == MessageType.Event),
                ops.filter(lambda msg: msg.parsed % 2 == 0),
            )
            .subscribe(
                lambda msg: print(
                    f"Rx:{msg.timestamp:.6f}  {msg.address}  {msg.message_type.name:<5s}  {msg.parsed}"
                )
            )
        )

        dev.subscribe_all(print_event)
        print(f"Listening for events on {PORT}. Press Ctrl+C to stop.\n")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nStopping.")
            disposable.dispose()
