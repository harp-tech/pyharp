from __future__ import annotations  # enable subscriptable type hints for lists.

import logging
import queue
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import serial

from pyharp.base import CommonRegisters
from pyharp.device_names import device_names
from pyharp.harp_serial import HarpSerial
from pyharp.messages import HarpMessage, ReplyHarpMessage


class DeviceMode(Enum):
    Standby = 0
    Active = 1
    Reserved = 2
    Speed = 3


class Device:
    """
    https://github.com/harp-tech/protocol/blob/master/Device%201.1%201.0%2020220402.pdf
    """

    _ser: HarpSerial
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
    DEVICE_NAME: str

    TIMEOUT_S = 1.0

    def __init__(
        self,
        serial_port: str,
        dump_file_path: Optional[str] = None,
        read_timeout_s=1,
    ):
        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._serial_port = serial_port
        if dump_file_path is None:
            self._dump_file_path = None
        else:
            self._dump_file_path = Path() / dump_file_path
        self.read_timeout_s = read_timeout_s
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
        print(f"* Who am I: ({self.WHO_AM_I}) {self.WHO_AM_I_DEVICE}")
        print(f"* HW version: {self.HW_VERSION_H}.{self.HW_VERSION_L}")
        print(f"* Assembly version: {self.ASSEMBLY_VERSION}")
        print(f"* HARP version: {self.HARP_VERSION_H}.{self.HARP_VERSION_L}")
        print(f"* Firmware version: {self.FIRMWARE_VERSION_H}.{self.FIRMWARE_VERSION_L}")
        print(f"* Device user name: {self.DEVICE_NAME}")
        print(f"* Mode: {self.read_device_mode().name}")

    def read(self):
        pass

    def connect(self) -> None:
        self._ser = HarpSerial(
            self._serial_port,  # "/dev/tty.usbserial-A106C8O9"
            baudrate=1000000,
            timeout=self.__class__.TIMEOUT_S,
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
        #print(str(reply))
        return reply.payload_as_int()

    def read_who_am_i_device(self) -> str:
        address = CommonRegisters.WHO_AM_I

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU16(address).frame, dump=False
        )
        #print(str(reply))

        return device_names.get(reply.payload_as_int())

    def read_hw_version_h(self) -> int:
        address = CommonRegisters.HW_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )
        #print(str(reply))

        return reply.payload_as_int()

    def read_hw_version_l(self) -> int:
        address = CommonRegisters.HW_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )
        #print(str(reply))

        return reply.payload_as_int()

    def read_assembly_version(self) -> int:
        address = CommonRegisters.ASSEMBLY_VERSION

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )
        #print(str(reply))

        return reply.payload_as_int()

    def read_harp_h_version(self) -> int:
        address = CommonRegisters.HARP_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )
        #print(str(reply))

        return reply.payload_as_int()

    def read_harp_l_version(self) -> int:
        address = CommonRegisters.HARP_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )
        #print(str(reply))

        return reply.payload_as_int()

    def read_fw_h_version(self) -> int:
        address = CommonRegisters.FIRMWARE_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )
        #print(str(reply))

        return reply.payload_as_int()

    def read_fw_l_version(self) -> int:
        address = CommonRegisters.FIRMWARE_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
)
        #print(str(reply))

        return reply.payload_as_int()

    def read_device_name(self) -> str:
        address = CommonRegisters.DEVICE_NAME

        # reply: Optional[bytes] = self.send(HarpMessage.ReadU8(address).frame, 13 + 24)
        reply: ReplyHarpMessage = self.send(
            HarpMessage.ReadU8(address).frame, dump=False
        )
        #print(str(reply))

        return reply.payload_as_string()

    def read_device_mode(self) -> DeviceMode:
        address = CommonRegisters.OPERATION_CTRL
        reply = self.send(HarpMessage.ReadU8(address).frame)
        return DeviceMode(reply.payload_as_int() & 0x03)

    def dump_registers(self) -> list:
        """Assert the DUMP bit to dump the values of all core and app registers
        as Harp Read Reply Messages.
        """
        address = CommonRegisters.OPERATION_CTRL
        reg_value = self.send(HarpMessage.ReadU8(address).frame).payload_as_int()
        reg_value |= 0x08  # Assert DUMP bit
        self._ser.write(HarpMessage.WriteU8(address, reg_value).frame)
        replies = []
        while True:
            msg = self._read()
            if msg is not None:
                replies.append(msg)
            else:
                break
        return replies

# TODO: Not sure if we want to implement these. Delete if no.
    def set_mode(self, mode: DeviceMode) -> ReplyHarpMessage:
        """Change the device's OPMODE. Reply can be ignored."""
        address = CommonRegisters.OPERATION_CTRL
        # Read register first.
        reg_value = self.send(HarpMessage.ReadU8(address).frame).payload_as_int()
        reg_value &= ~0x03 # mask off old mode.
        reg_value |= mode.value
        reply = self.send(HarpMessage.WriteU8(address, reg_value).frame)
        return reply

    def enable_status_led(self):
        """enable the device's status led if one exists."""
        address = CommonRegisters.OPERATION_CTRL
        # Read register first.
        reg_value = self.send(HarpMessage.ReadU8(address).frame).payload_as_int()
        reg_value |= (1 << 5)
        reply = self.send(HarpMessage.WriteU8(address, reg_value).frame)

    def disable_status_led(self):
        """disable the device's status led if one exists."""
        address = CommonRegisters.OPERATION_CTRL
        # Read register first.
        reg_value = self.send(HarpMessage.ReadU8(address).frame).payload_as_int()
        reg_value &= ~(1 << 5)
        reply = self.send(HarpMessage.WriteU8(address, reg_value).frame)

    def enable_alive_en(self):
        """Enable ALIVE_EN such that the device sends an event each second."""
        address = CommonRegisters.OPERATION_CTRL
        # Read register first.
        reg_value = self.send(HarpMessage.ReadU8(address).frame).payload_as_int()
        reg_value |= (1 << 7)
        reply = self.send(HarpMessage.WriteU8(address, reg_value).frame)

    def disable_alive_en(self):
        """disable ALIVE_EN such that the device does not send an event each second."""
        address = CommonRegisters.OPERATION_CTRL
        # Read register first.
        reg_value = self.send(HarpMessage.ReadU8(address).frame).payload[0]
        reg_value &= ((1<< 7) ^ 0xFF) # bitwise ~ operator substitute for Python ints.
        reply = self.send(HarpMessage.WriteU8(address, reg_value).frame)

    def reset_device(self):
        address = CommonRegisters.RESET_DEV
        # reset_value = 0xFF & (1<<ResetDevOffsets.RST_DEV_OFFSET)
        reset_value = 0x01
        # reply = self.send(HarpMessage.WriteU8(address,reset_value).frame)
        self._ser.write(HarpMessage.WriteU8(address, reset_value).frame)

    def send(self, message_bytes: bytearray, dump: bool = True) -> ReplyHarpMessage:
        """Send a harp message; return the device's reply."""
        #print(f"Sending: {repr(message_bytes)}")
        self._ser.write(message_bytes)

        # TODO: handle case where read is None
        reply: ReplyHarpMessage = self._read()

        if dump and self._dump_file_path is not None:
            self._dump_reply(reply.frame)

        return reply

    def _read(self) -> Union[ReplyHarpMessage, None]:
        """(Blocking) Read an incoming serial message."""
        try:
            return self._ser.msg_q.get(block=True, timeout=self.read_timeout_s)
        except queue.Empty:
            return None
        
    def _dump_reply(self, reply: bytes):
        assert self._dump_file_path is not None
        with self._dump_file_path.open(mode="ab") as f:
            f.write(reply)

    def get_events(self) -> list[ReplyHarpMessage]:
        """Get all events from the event queue."""
        msgs = []
        while True:
            try:
                msgs.append(self._ser.event_q.get(timeout=False))
            except queue.Empty:
                break
        return msgs

    def event_count(self) -> int:
        """Get the number of events in the event queue."""
        return self._ser.event_q.qsize()