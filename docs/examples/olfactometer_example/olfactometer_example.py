import random
import time
from threading import Event, Thread

from serial import SerialException

from pyharp.communication.device import Device, OperationMode
from pyharp.protocol import MessageType, PayloadType
from pyharp.protocol.messages import HarpMessage

SERIAL_PORT = (
    "/dev/ttyUSB0"  # or "COMx" in Windows ("x" is the number of the serial port)
)


def print_events(device, stop_flag):
    while not stop_flag.is_set():
        for msg in device.get_events():
            if (
                msg.address == 48
                or msg.address == 49
                or msg.address == 50
                or msg.address == 51
                or msg.address == 52
            ):
                print(msg.address - 48)
                print(msg.payload[0])
                print()


def main():
    # Open connection
    device = Device(SERIAL_PORT)
    time.sleep(1)

    stop_flag = Event()

    # Check if the device is a Harp Olfactometer
    if not device.WHO_AM_I == 1140:
        raise SerialException("This is not a Harp Olfactometer.")

    device.set_mode(OperationMode.ACTIVE)

    # Enable flow
    device.send(HarpMessage.create(MessageType.WRITE, 32, PayloadType.U8, 0x01))

    # Initialize thread for events
    events_thread = Thread(
        target=print_events,
        args=(
            device,
            stop_flag,
        ),
    )
    events_thread.start()

    # Set the valves to a random flow
    device.send(
        HarpMessage.create(
            MessageType.WRITE, 42, PayloadType.Float, int(random.random() * 100)
        )
    )
    device.send(
        HarpMessage.create(
            MessageType.WRITE, 43, PayloadType.Float, int(random.random() * 100)
        )
    )
    device.send(
        HarpMessage.create(
            MessageType.WRITE, 44, PayloadType.Float, int(random.random() * 100)
        )
    )
    device.send(
        HarpMessage.create(
            MessageType.WRITE, 45, PayloadType.Float, int(random.random() * 100)
        )
    )

    # Open every odor valve, one at a time every 5 seconds
    device.send(HarpMessage.create(MessageType.WRITE, 68, PayloadType.Float, 0x01))

    time.sleep(5)

    device.send(HarpMessage.create(MessageType.WRITE, 69, PayloadType.Float, 0x01))
    device.send(HarpMessage.create(MessageType.WRITE, 68, PayloadType.Float, 0x02))

    time.sleep(5)

    device.send(HarpMessage.create(MessageType.WRITE, 69, PayloadType.Float, 0x02))
    device.send(HarpMessage.create(MessageType.WRITE, 68, PayloadType.Float, 0x04))

    time.sleep(5)

    device.send(HarpMessage.create(MessageType.WRITE, 69, PayloadType.Float, 0x04))
    device.send(HarpMessage.create(MessageType.WRITE, 68, PayloadType.Float, 0x08))

    time.sleep(5)

    device.send(HarpMessage.create(MessageType.WRITE, 69, PayloadType.Float, 0x08))

    time.sleep(5)

    # Disable flow
    device.send(HarpMessage.create(MessageType.WRITE, 32, PayloadType.Float, 0x00))

    time.sleep(1)

    stop_flag.set()
    events_thread.join()

    # Close connection
    device.disconnect()


if __name__ == "__main__":
    main()
