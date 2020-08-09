import serial

from typing import Optional
from pyharp.messages import HarpMessage, ReplyHarpMessage
from pyharp.device import Device

DEFAULT_ADDRESS = 42


def test_create_device() -> None:
    # open serial connection and load info
    device = Device("/dev/tty.usbserial-A106C8O9")
    assert device._ser.is_open
    device.info()
    device.disconnect()
    assert not device._ser.is_open


def test_read_U8() -> None:
    # open serial connection and load info
    device = Device("/dev/tty.usbserial-A106C8O9", "dump.bin")

    # read register 38
    register: int = 38
    read_size: int = 35  # TODO: automatically calculate this!

    read_message = HarpMessage.ReadU8(register)
    reply: ReplyHarpMessage = device.send(read_message.frame)
    assert reply is not None
    # assert reply.payload_as_int() == write_value

    print(reply)
    assert device._dump_file_path.exists()
    device.disconnect()


def test_U8() -> None:
    # open serial connection and load info
    device = Device("/dev/tty.usbserial-A106C8O9", "dump.txt")
    assert device._dump_file_path.exists()

    register: int = 38
    read_size: int = 20  # TODO: automatically calculate this!
    write_value: int = 65

    # assert reply[11] == 0  # what is the default register value?!

    # write 65 on register 38
    write_message = HarpMessage.WriteU8(register, write_value)
    reply : ReplyHarpMessage = device.send(write_message.frame)
    assert reply is not None

    # read register 38
    read_message = HarpMessage.ReadU8(register)
    reply = device.send(read_message.frame)
    assert reply is not None
    assert reply.payload_as_int() == write_value

    device.disconnect()


# def test_read_hw_version_integration() -> None:
#
#     # serial settings
#     ser = serial.Serial(
#         "/dev/tty.usbserial-A106C8O9",
#         baudrate=1000000,
#         timeout=5,
#         parity=serial.PARITY_NONE,
#         stopbits=1,
#         bytesize=8,
#         rtscts=True,
#     )
#
#     assert ser.is_open
#
#     ser.write(b"\x01\x04\x01\xff\x01\x06")  # read HW major version (register 1)
#     ser.write(b"\x01\x04\x02\xff\x01\x07")  # read HW minor version (register 2)
#     # print(f"In waiting: <{ser.in_waiting}>")
#
#     data = ser.read(100)
#     print(f"Data: {data}")
#     ser.close()
#     assert not ser.is_open
#
#     # assert data[0] == '\t'
