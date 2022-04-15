import serial
from typing import Optional
from pathlib import Path

from pyharp.messages import HarpMessage, ReplyHarpMessage
from pyharp.messages import CommonRegisters
from pyharp.device_names import device_names


class Device:
    """
    https://github.com/harp-tech/protocol/blob/master/Device%201.1%201.0%2020220402.pdf
    """

    _ser: serial.Serial
    _dump_file_path: Path

    WHO_AM_I: int
    WHO_AM_I_DEVICE: str
    HW_VERSION_H: int
    HW_VERSION_L: int
    ASSEMBLY_VERSION: int
    HARP_VERSION_H: int
    HARP_VERSION_L: int
    FIRMWARE_VERSION_H: int
    FIRMWARE_VERSION_L: int
    # TIMESTAMP_SECOND = 0x08
    # TIMESTAMP_MICRO = 0x09
    # OPERATION_CTRL = 0x0A
    # RESET_DEV = 0x0B
    DEVICE_NAME: str

    def __init__(self, serial_port: str, dump_file_path: Optional[str] = None):
        self._serial_port = serial_port
        if dump_file_path is None:
            self._dump_file_path = None
        else:
            self._dump_file_path = Path() / dump_file_path
        self.connect()
        self.load()

    def load(self) -> None:
        self.WHO_AM_I = self.read_who_am_i()
        self.WHO_AM_I_DEVICE = self.read_who_am_i_device()
        self.HW_VERSION_H = self.read_hw_version_h()
        self.HW_VERSION_L = self.read_hw_version_l()
        self.ASSEMBLY_VERSION = self.read_assembly_version()
        self.HARP_VERSION_H = self.read_harp_h_version()
        self.HARP_VERSION_L = self.read_harp_l_version()
        self.FIRMWARE_VERSION_H = self.read_fw_h_version()
        self.FIRMWARE_VERSION_L = self.read_fw_l_version()
        self.DEVICE_NAME = self.read_device_name()

    def info(self) -> None:
        print("Device info:")
        #print(f"* Who am I (ID): {self.WHO_AM_I}")
        #print(f"* Who am I (Device): {self.WHO_AM_I_DEVICE}")
        print(f"* Who am I: ({self.WHO_AM_I}) {self.WHO_AM_I_DEVICE}")
        print(f"* HW version: {self.HW_VERSION_H}.{self.HW_VERSION_L}")
        print(f"* Assembly version: {self.ASSEMBLY_VERSION}")
        print(f"* HARP version: {self.HARP_VERSION_H}.{self.HARP_VERSION_L}")
        print(
            f"* Firmware version: {self.FIRMWARE_VERSION_H}.{self.FIRMWARE_VERSION_L}"
        )
        print(f"* Device user name: {self.DEVICE_NAME}")

    def read(self):
        pass

    def connect(self) -> None:
        self._ser = serial.Serial(
            self._serial_port,  # "/dev/tty.usbserial-A106C8O9"
            baudrate=1000000,
            timeout=1,
            parity=serial.PARITY_NONE,
            stopbits=1,
            bytesize=8,
            rtscts=True,
        )

    def disconnect(self) -> None:
        self._ser.close()

    def read_who_am_i(self) -> int:
        address = CommonRegisters.WHO_AM_I

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU16(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_who_am_i_device(self) -> str:
        address = CommonRegisters.WHO_AM_I

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU16(address).frame, dump=False
        )

        return device_names.get(reply.payload_as_int())

    def read_hw_version_h(self) -> int:
        address = CommonRegisters.HW_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_hw_version_l(self) -> int:
        address = CommonRegisters.HW_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_assembly_version(self) -> int:
        address = CommonRegisters.ASSEMBLY_VERSION

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_harp_h_version(self) -> int:
        address = CommonRegisters.HARP_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_harp_l_version(self) -> int:
        address = CommonRegisters.HARP_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_fw_h_version(self) -> int:
        address = CommonRegisters.FIRMWARE_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_fw_l_version(self) -> int:
        address = CommonRegisters.FIRMWARE_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_int()

    def read_device_name(self) -> str:
        address = CommonRegisters.DEVICE_NAME

        # reply: Optional[bytes] = self.send(HarpMessage.ReadU8(address).frame, 13 + 24)
        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )

        return reply.payload_as_string()

    def send(self, message_bytes: bytearray, dump: bool = True) -> ReplyHarpMessage:

        self._ser.write(message_bytes)

        # TODO: handle case where read is None

        message_type = self._ser.read(1)[0]  # byte array with only one byte
        message_length = self._ser.read(1)[0]
        message_content = self._ser.read(message_length)

        frame = bytearray()
        frame.append(message_type)
        frame.append(message_length)
        frame += message_content

        reply: ReplyHarpMessage = HarpMessage.parse(frame)

        if dump:
            self._dump_reply(reply.frame)

        return reply

    def _dump_reply(self, reply: bytes):
        assert self._dump_file_path is not None
        with self._dump_file_path.open(mode="ab") as f:
            f.write(reply)
