from __future__ import annotations  # enable subscriptable type hints for lists.

import logging
import queue
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

import serial

from pyharp.base import CommonRegisters, PayloadType
from pyharp.device_names import device_names
from pyharp.harp_serial import HarpSerial
from pyharp.messages import ReadHarpMessage, ReplyHarpMessage, WriteHarpMessage


class DeviceMode(Enum):
    Standby = 0
    Active = 1
    Reserved = 2
    Speed = 3


class Device:
    """
    The `Device` class provides the interface for interacting with Harp devices. This implementation of the Harp device was based on the official documentation available on the [harp-tech website](https://harp-tech.org/protocol/Device.html).

    Attributes
    ----------
    WHO_AM_I : int
        the device ID number. A list of devices can be found [here](https://github.com/harp-tech/protocol/blob/main/whoami.md)
    DEFAULT_DEVICE_NAME : str
        the device name, i.e. "Behavior". This name is derived by cross-referencing the `WHO_AM_I` identifier with the corresponding device name in the `device_names` dictionary
    HW_VERSION_H : int
        the major hardware version
    HW_VERSION_L : int
        the minor hardware version
    ASSEMBLY_VERSION : int
        the version of the assembled components
    HARP_VERSION_H : int
        the major Harp core version
    HARP_VERSION_L : int
        the minor Harp core version
    FIRMWARE_VERSION_H : int
        the major firmware version
    FIRMWARE_VERSION_L : int
        the minor firmware version
    DEVICE_NAME : str
        the device name stored in the Harp device
    SERIAL_NUMBER : int, optional
        the serial number of the device
    """

    WHO_AM_I: int
    DEFAULT_DEVICE_NAME: str
    HW_VERSION_H: int
    HW_VERSION_L: int
    ASSEMBLY_VERSION: int
    HARP_VERSION_H: int
    HARP_VERSION_L: int
    FIRMWARE_VERSION_H: int
    FIRMWARE_VERSION_L: int
    DEVICE_NAME: str
    SERIAL_NUMBER: int

    TIMEOUT_S = 1.0

    def __init__(
        self,
        serial_port: str,
        dump_file_path: Optional[str] = None,
        read_timeout_s=1,
    ):
        """
        Parameters
        ----------
        serial_port : str
            the serial port used to establish the connection with the Harp device. It must be denoted as `ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port
        dump_file_path: str, optional
            the binary file to which all Harp messages will be written
        read_timeout_s: float, optional
            _TODO_
        """
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
        """
        Loads the data stored in the device's common registers.
        """
        self.WHO_AM_I = self._read_who_am_i()
        self.DEFAULT_DEVICE_NAME = self._read_default_device_name()
        self.HW_VERSION_H = self._read_hw_version_h()
        self.HW_VERSION_L = self._read_hw_version_l()
        self.ASSEMBLY_VERSION = self._read_assembly_version()
        self.HARP_VERSION_H = self._read_harp_h_version()
        self.HARP_VERSION_L = self._read_harp_l_version()
        self.FIRMWARE_VERSION_H = self._read_fw_h_version()
        self.FIRMWARE_VERSION_L = self._read_fw_l_version()
        self.DEVICE_NAME = self._read_device_name()
        self.SERIAL_NUMBER = self._read_serial_number()

    def info(self) -> None:
        """
        Prints the device information.
        """
        print("Device info:")
        print(f"* Who am I: ({self.WHO_AM_I}) {self.DEFAULT_DEVICE_NAME}")
        print(f"* HW version: {self.HW_VERSION_H}.{self.HW_VERSION_L}")
        print(f"* Assembly version: {self.ASSEMBLY_VERSION}")
        print(f"* HARP version: {self.HARP_VERSION_H}.{self.HARP_VERSION_L}")
        print(f"* Firmware version: {self.FIRMWARE_VERSION_H}.{self.FIRMWARE_VERSION_L}")
        print(f"* Device user name: {self.DEVICE_NAME}")
        print(f"* Serial number: {self.SERIAL_NUMBER}")
        print(f"* Mode: {self.read_device_mode().name}")

    def connect(self) -> None:
        """
        Connects to the Harp device.
        """
        self._ser = HarpSerial(
            self._serial_port,  # "/dev/tty.usbserial-A106C8O9"
            baudrate=1000000,
            timeout=self.TIMEOUT_S,
            parity=serial.PARITY_NONE,
            stopbits=1,
            bytesize=8,
            rtscts=True,
        )

    def disconnect(self) -> None:
        """
        Disconnects from the Harp device.
        """
        self._ser.close()

    def _read_device_mode(self) -> DeviceMode:
        """
        Reads the current operation mode of the Harp device.

        Returns
        -------
        DeviceMode
            the current device mode
        """
        address = CommonRegisters.OPERATION_CTRL
        reply = self.read_u8(address)
        return DeviceMode(reply.payload_as_int() & 0x03)

    def dump_registers(self) -> list:
        """
        Asserts the DUMP bit to dump the values of all core and app registers
        as Harp Read Reply Messages. More information on the DUMP bit can be found [here](https://harp-tech.org/protocol/Device.html#r_operation_ctrl-u16--operation-mode-configuration).

        Returns
        -------
        list
            the list containing the reply Harp messages for all the device's registers
        """
        address = CommonRegisters.OPERATION_CTRL
        reg_value = self.read_u8(address).payload_as_int()
        reg_value |= 0x08  # Assert DUMP bit
        self._ser.write(WriteHarpMessage(PayloadType.U8, address, reg_value).frame)
        replies = []
        while True:
            msg = self._read()
            if msg is not None:
                replies.append(msg)
            else:
                break
        return replies

    def set_mode(self, mode: DeviceMode) -> ReplyHarpMessage:
        """
        Sets the operation mode of the device.

        Parameters
        ----------
        mode : DeviceMode
            the new device mode value

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.read_u8(address).payload_as_int()
        reg_value &= ~0x03 # mask off old mode.
        reg_value |= mode.value
        reply = self.send(WriteHarpMessage(PayloadType.U8, address, reg_value).frame)
        return reply

    def enable_status_led(self) -> ReplyHarpMessage:
        """
        Enables the device's status led.

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.read_u8(address).payload_as_int()
        reg_value |= (1 << 5)
        reply = self.send(WriteHarpMessage(PayloadType.U8, address, reg_value).frame)

    def disable_status_led(self) -> ReplyHarpMessage:
        """
        Disables the device's status led.

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.read_u8(address).payload_as_int()
        reg_value &= ~(1 << 5)
        reply = self.send(WriteHarpMessage(PayloadType.U8, address, reg_value).frame)

    def enable_alive_en(self) -> ReplyHarpMessage:
        """
        Enables the ALIVE_EN bit so that the device sends an event each second. More information on the ALIVE_EN bit can be found [here](https://harp-tech.org/protocol/Device.html#r_operation_ctrl-u16--operation-mode-configuration).

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.read_u8(address).payload_as_int()
        reg_value |= (1 << 7)
        reply = self.send(WriteHarpMessage(PayloadType.U8, address, reg_value).frame)

    def disable_alive_en(self) -> ReplyHarpMessage:
        """
        Disables the ALIVE_EN bit so that the device does not send an event each second. More information on the ALIVE_EN bit can be found [here](https://harp-tech.org/protocol/Device.html#r_operation_ctrl-u16--operation-mode-configuration).

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.read_u8(address).payload[0]
        reg_value &= (1 << 7) ^ 0xFF  # bitwise ~ operator substitute for Python ints.
        reply = self.send(WriteHarpMessage(PayloadType.U8, address, reg_value).frame)

    def reset_device(self):
        address = CommonRegisters.RESET_DEV
        reset_value = 0x01
        self._ser.write(WriteHarpMessage(PayloadType.U8, address, reset_value).frame)

    def send(self, message_bytes: bytearray, dump: bool = True) -> ReplyHarpMessage:
        """
        Sends a Harp message.

        Parameters
        ----------
        message_bytes : bytearray
            the bytearray containing the message to be sent to the device
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        self._ser.write(message_bytes)

        # TODO: handle case where read is None
        reply: ReplyHarpMessage = self._read()

        if dump and self._dump_file_path is not None:
            self._dump_reply(reply.frame)

        return reply

    def _read(self) -> Union[ReplyHarpMessage, None]:
        """
        Reads an incoming serial message in a blocking way.

        Returns
        -------
        Union[ReplyHarpMessage, None]
            the incoming Harp message in case it exists
        """
        try:
            return self._ser.msg_q.get(block=True, timeout=self.read_timeout_s)
        except queue.Empty:
            return None

    def _dump_reply(self, reply: bytes):
        """
        Dumps the reply to a Harp message in the dump file in case it exists.
        """
        # TODO: try to handle a None _dump_file_path in a different way
        assert self._dump_file_path is not None
        with self._dump_file_path.open(mode="ab") as f:
            f.write(reply)

    def get_events(self) -> list[ReplyHarpMessage]:
        """
        Gets all events from the event queue.

        Returns
        -------
        list
            the list containing every Harp event message that were on the queue
        """
        msgs = []
        while True:
            try:
                msgs.append(self._ser.event_q.get(timeout=False))
            except queue.Empty:
                break
        return msgs

    def event_count(self) -> int:
        """
        Gets the number of events in the event queue.

        Returns
        -------
        int
            the number of events in the event queue
        """
        return self._ser.event_q.qsize()

    def read_u8(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U8.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.U8, address=address).frame, dump
        )

    def read_s8(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S8.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.S8, address=address).frame, dump
        )

    def read_u16(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U16.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.U16, address=address).frame, dump
        )

    def read_s16(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S16.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.S16, address=address).frame, dump
        )

    def read_u32(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U32.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.U32, address=address).frame, dump
        )

    def read_s32(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S32.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.S32, address=address).frame, dump
        )

    def read_u64(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U64.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.U64, address=address).frame, dump
        )

    def read_s64(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S64.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.S64, address=address).frame, dump
        )

    def read_float(self, address: int, dump: bool = True) -> ReplyHarpMessage:
        """
        Reads the value of a register of type Float.

        Parameters
        ----------
        address : int
            the register to be read
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            ReadHarpMessage(payload_type=PayloadType.Float, address=address).frame, dump
        )

    def write_u8(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U8.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.U8,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_s8(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S8.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.S8,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_u16(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U16.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.U16,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_s16(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S16.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.S16,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_u32(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U32.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.U32,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_s32(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S32.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.S32,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_u64(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U64.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.U64,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_s64(
        self, address: int, value: int | List[int], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S64.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.S64,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def write_float(
        self, address: int, value: float | List[float], dump: bool = True
    ) -> ReplyHarpMessage:
        """
        Writes the value of a register of type Float.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | List[int]
            the value to be written to the register
        dump : bool, optional
            indicates whether the reply message should be dumped or not

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            WriteHarpMessage(
                payload_type=PayloadType.Float,
                address=address,
                value=value,
            ).frame,
            dump=dump,
        )

    def _read_who_am_i(self) -> int:
        """
        Reads the value stored in the `WHO_AM_I` register.

        Returns
        -------
        int
            the value of the `WHO_AM_I` register.
        """
        address = CommonRegisters.WHO_AM_I

        reply: ReplyHarpMessage = self.read_u16(address, dump=False)

        return reply.payload_as_int()

    def _read_default_device_name(self) -> str:
        """
        Returns the `DEFAULT_DEVICE_NAME` by cross-referencing the `WHO_AM_I` with the corresponding device name in the `device_names` dictionary.

        Returns
        -------
        str
            the default device name.
        """
        return device_names.get(self.WHO_AM_I, "Unknown device")

    def _read_hw_version_h(self) -> int:
        """
        Reads the value stored in the `HW_VERSION_H` register.

        Returns
        -------
        int
            the value of the `HW_VERSION_H` register.
        """
        address = CommonRegisters.HW_VERSION_H

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_int()

    def _read_hw_version_l(self) -> int:
        """
        Reads the value stored in the `HW_VERSION_L` register.

        Returns
        -------
        int
            the value of the `HW_VERSION_L` register.
        """
        address = CommonRegisters.HW_VERSION_L

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_int()

    def _read_assembly_version(self) -> int:
        """
        Reads the value stored in the `ASSEMBLY_VERSION` register.

        Returns
        -------
        int
            the value of the `ASSEMBLY_VERSION` register.
        """
        address = CommonRegisters.ASSEMBLY_VERSION

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_int()

    def _read_harp_h_version(self) -> int:
        address = CommonRegisters.HARP_VERSION_H

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_int()

    def _read_harp_l_version(self) -> int:
        address = CommonRegisters.HARP_VERSION_L

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_int()

    def _read_fw_h_version(self) -> int:
        address = CommonRegisters.FIRMWARE_VERSION_H

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_int()

    def _read_fw_l_version(self) -> int:
        address = CommonRegisters.FIRMWARE_VERSION_L

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_int()

    def _read_device_name(self) -> str:
        """
        Reads the value stored in the `DEVICE_NAME` register.

        Returns
        -------
        int
            the value of the `DEVICE_NAME` register.
        """
        address = CommonRegisters.DEVICE_NAME

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        return reply.payload_as_string()

    def _read_serial_number(self) -> int:
        """
        Reads the value stored in the `SERIAL_NUMBER` register.

        Returns
        -------
        int
            the value of the `SERIAL_NUMBER` register.
        """
        address = CommonRegisters.SERIAL_NUMBER

        reply: ReplyHarpMessage = self.read_u8(address, dump=False)

        if reply.has_error():
            return 0

        return reply.payload_as_int()

    def __enter__(self):
        """
        Support for using Device with 'with' statement.

        Returns
        -------
        Device
            The Device instance
        """
        # Connection is already established in __init__
        # but we could add additional setup if needed
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Cleanup resources when exiting the 'with' block.

        Parameters
        ----------
        exc_type : Exception type or None
            Type of the exception that caused the context to be exited
        exc_val : Exception or None
            Exception instance that caused the context to be exited
        exc_tb : traceback or None
            Traceback if an exception occurred
        """
        self.disconnect()
        # Return False to propagate exceptions that occurred in the with block
        return False
