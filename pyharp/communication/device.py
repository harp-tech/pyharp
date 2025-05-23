from __future__ import annotations  # enable subscriptable type hints for lists.

import logging
import queue
from io import BufferedWriter
from pathlib import Path
from typing import Optional, Union

import serial

from pyharp.communication.harp_serial import HarpSerial
from pyharp.protocol import (
    ClockConfig,
    CommonRegisters,
    MessageType,
    OperationCtrl,
    OperationMode,
    PayloadType,
    ResetMode,
)
from pyharp.protocol.device_names import device_names
from pyharp.protocol.messages import HarpMessage, ReplyHarpMessage


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
    CLOCK_CONFIG: int
    TIMESTAMP_OFFSET: int

    _ser: HarpSerial
    _dump_file_path: Path
    _dump_file: Optional[BufferedWriter] = None
    _read_timeout_s: float

    _TIMEOUT_S: float = 1.0

    def __init__(
        self,
        serial_port: str,
        dump_file_path: Optional[str] = None,
        read_timeout_s: float = 1,
    ):
        """
        Parameters
        ----------
        serial_port : str
            the serial port used to establish the connection with the Harp device. It must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port
        dump_file_path: str, optional
            the binary file to which all Harp messages will be written
        read_timeout_s: float, optional
            _TODO_
        """
        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._serial_port = serial_port
        self._dump_file_path = dump_file_path
        if dump_file_path is not None:
            self._dump_file_path = Path() / dump_file_path
        self._read_timeout_s = read_timeout_s

        # Connect to the Harp device and load the data stored in the device's common registers
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
        self.HARP_VERSION_H = self._read_harp_version_h()
        self.HARP_VERSION_L = self._read_harp_version_l()
        self.FIRMWARE_VERSION_H = self._read_fw_version_h()
        self.FIRMWARE_VERSION_L = self._read_fw_version_l()
        self.DEVICE_NAME = self._read_device_name()
        self.SERIAL_NUMBER = self._read_serial_number()
        self.CLOCK_CONFIG = self._read_clock_config()
        self.TIMESTAMP_OFFSET = self._read_timestamp_offset()

    def info(self) -> None:
        """
        Prints the device information.
        """
        print("Device info:")
        print(f"* Who am I: ({self.WHO_AM_I}) {self.DEFAULT_DEVICE_NAME}")
        print(f"* HW version: {self.HW_VERSION_H}.{self.HW_VERSION_L}")
        print(f"* Assembly version: {self.ASSEMBLY_VERSION}")
        print(f"* HARP version: {self.HARP_VERSION_H}.{self.HARP_VERSION_L}")
        print(
            f"* Firmware version: {self.FIRMWARE_VERSION_H}.{self.FIRMWARE_VERSION_L}"
        )
        print(f"* Device user name: {self.DEVICE_NAME}")
        print(f"* Serial number: {self.SERIAL_NUMBER}")
        print(f"* Mode: {self._read_device_mode().name}")

    def connect(self) -> None:
        """
        Connects to the Harp device.
        """
        self._ser = HarpSerial(
            self._serial_port,  # "/dev/tty.usbserial-A106C8O9"
            baudrate=1000000,
            timeout=self._TIMEOUT_S,
            parity=serial.PARITY_NONE,
            stopbits=1,
            bytesize=8,
            rtscts=True,
        )

        # open file if it is defined
        if self._dump_file_path is not None:
            self._dump_file = open(self._dump_file_path, "ab")

    def disconnect(self) -> None:
        """
        Disconnects from the Harp device.
        """
        # close file if it exists
        if self._dump_file:
            self._dump_file.close()
            self._dump_file = None

        self._ser.close()

    def _read_device_mode(self) -> OperationMode:
        """
        Reads the current operation mode of the Harp device.

        Returns
        -------
        DeviceMode
            the current device mode
        """
        address = CommonRegisters.OPERATION_CTRL
        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))
        return OperationMode(reply.payload & OperationCtrl.OP_MODE)

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
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        ).payload
        # Assert DUMP bit
        reg_value |= OperationCtrl.DUMP
        self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        # Receive the contents of all registers as Harp Read Reply Messages
        replies = []
        while True:
            msg = self._read()
            if msg is not None:
                replies.append(msg)
            else:
                break
        return replies

    def set_mode(self, mode: OperationMode) -> ReplyHarpMessage:
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
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        ).payload

        # Clear old operation mode
        reg_value &= ~OperationCtrl.OP_MODE

        # Set new operation mode
        reg_value |= mode
        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply

    def alive_en(self, enable: bool) -> bool:
        """
        Sets the ALIVE_EN bit of the device.

        Parameters
        ----------
        enable : bool
            If True, enables the ALIVE_EN bit. If False, disables it.

        Returns
        -------
        bool
            True if the operation was successful, False otherwise.
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        ).payload

        if enable:
            reg_value |= OperationCtrl.ALIVE_EN
        else:
            reg_value &= ~OperationCtrl.ALIVE_EN

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply

    def op_led_en(self, enable: bool) -> bool:
        """
        Sets the operation LED of the device.

        Parameters
        ----------
        enable : bool
            If True, enables the operation LED. If False, disables it.

        Returns
        -------
        bool
            True if the operation was successful, False otherwise.
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        ).payload

        if enable:
            reg_value |= OperationCtrl.OPLEDEN
        else:
            reg_value &= ~OperationCtrl.OPLEDEN

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply

    def status_led(self, enable: bool) -> bool:
        """
        Sets the status led of the device.

        Parameters
        ----------
        enable : bool
            If True, enables the status led. If False, disables it.

        Returns
        -------
        bool
            True if the operation was successful, False otherwise.
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        ).payload

        if enable:
            reg_value |= OperationCtrl.STATUS_LED
        else:
            reg_value &= ~OperationCtrl.STATUS_LED

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply

    def mute_reply(self, enable: bool) -> bool:
        """
        Sets the MUTE_REPLY bit of the device.

        Parameters
        ----------
        enable : bool
            If True, the Replies to all the Commands are muted. If False, un-mutes them.

        Returns
        -------
        bool
            True if the operation was successful, False otherwise.
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        ).payload

        if enable:
            reg_value |= OperationCtrl.MUTE_RPL
        else:
            reg_value &= ~OperationCtrl.MUTE_RPL

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply

    def reset_device(
        self, reset_mode: ResetMode = ResetMode.RST_DEF
    ) -> ReplyHarpMessage:
        """
        Resets the device and reboots with all the registers with the default values. Beware that the EEPROM will be erased. More information on the reset device register can be found [here](https://harp-tech.org/protocol/Device.html#r_reset_dev-u8--reset-device-and-save-non-volatile-registers).

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.RESET_DEV
        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reset_mode)
        )

        return reply

    def set_clock_config(self, clock_config: ClockConfig) -> ReplyHarpMessage:
        """
        Sets the clock configuration of the device.

        Parameters
        ----------
        clock_config : ClockConfig
            the clock configuration value

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.CLOCK_CONFIG
        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, clock_config)
        )

        return reply

    def set_timestamp_offset(self, timestamp_offset: int) -> ReplyHarpMessage:
        """
        When the value of this register is above 0 (zero), the device's timestamp will be offset by this amount. The register is sensitive to 500 microsecond increments. This register is non-volatile.

        Parameters
        ----------
        timestamp_offset : int
            the timestamp offset value

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        address = CommonRegisters.TIMESTAMP_OFFSET
        reply = self.send(
            HarpMessage.create(
                MessageType.WRITE, address, PayloadType.U8, timestamp_offset
            )
        )

        return reply

    def send(self, message: HarpMessage) -> Optional[ReplyHarpMessage]:
        """
        Sends a Harp message.

        Parameters
        ----------
        message_bytes : HarpMessage
            the HarpMessage containing the message to be sent to the device

        Returns
        -------
        Optional[ReplyHarpMessage]
            the reply to the Harp message or None if no reply is given
        """
        self._ser.write(message.frame)

        reply = self._read()
        if reply is None:
            return None

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
            return self._ser.msg_q.get(block=True, timeout=self._read_timeout_s)
        except queue.Empty:
            return None

    def _dump_reply(self, reply: bytes):
        """
        Dumps the reply to a Harp message in the dump file in case it exists.
        """
        if self._dump_file:
            self._dump_file.write(reply)

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

    def read_u8(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U8.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U8,
            )
        )

    def read_s8(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S8.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S8,
            )
        )

    def read_u16(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U16.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U16,
            )
        )

    def read_s16(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S16.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S16,
            )
        )

    def read_u32(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U32.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U32,
            )
        )

    def read_s32(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S32.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S32,
            )
        )

    def read_u64(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type U64.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U64,
            )
        )

    def read_s64(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type S64.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S64,
            )
        )

    def read_float(self, address: int) -> ReplyHarpMessage:
        """
        Reads the value of a register of type Float.

        Parameters
        ----------
        address : int
            the register to be read

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message that will contain the value read from the register
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.Float,
            )
        )

    def write_u8(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U8.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U8,
                value=value,
            )
        )

    def write_s8(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S8.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S8,
                value=value,
            )
        )

    def write_u16(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U16.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U16,
                value=value,
            )
        )

    def write_s16(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S16.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S16,
                value=value,
            )
        )

    def write_u32(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U32.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U32,
                value=value,
            )
        )

    def write_s32(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S32.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S32,
                value=value,
            )
        )

    def write_u64(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type U64.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U64,
                value=value,
            )
        )

    def write_s64(self, address: int, value: int | list[int]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type S64.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S64,
                value=value,
            )
        )

    def write_float(self, address: int, value: float | list[float]) -> ReplyHarpMessage:
        """
        Writes the value of a register of type Float.

        Parameters
        ----------
        address : int
            the register to be written on
        value: int | list[int]
            the value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            the reply to the Harp message
        """
        return self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.Float,
                value=value,
            )
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

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U16)
        )

        return reply.payload

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

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_hw_version_l(self) -> int:
        """
        Reads the value stored in the `HW_VERSION_L` register.

        Returns
        -------
        int
            the value of the `HW_VERSION_L` register.
        """
        address = CommonRegisters.HW_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_assembly_version(self) -> int:
        """
        Reads the value stored in the `ASSEMBLY_VERSION` register.

        Returns
        -------
        int
            the value of the `ASSEMBLY_VERSION` register.
        """
        address = CommonRegisters.ASSEMBLY_VERSION

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_harp_version_h(self) -> int:
        """
        Reads the value stored in the `HARP_VERSION_H` register.

        Returns
        -------
        int
            the value of the `HARP_VERSION_H` register.
        """
        address = CommonRegisters.HARP_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_harp_version_l(self) -> int:
        """
        Reads the value stored in the `HARP_VERSION_L` register.

        Returns
        -------
        int
            the value of the `HARP_VERSION_L` register.
        """
        address = CommonRegisters.HARP_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_fw_version_h(self) -> int:
        """
        Reads the value stored in the `FW_VERSION_H` register.

        Returns
        -------
        int
            the value of the `FW_VERSION_H` register.
        """
        address = CommonRegisters.FIRMWARE_VERSION_H

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_fw_version_l(self) -> int:
        """
        Reads the value stored in the `FW_VERSION_L` register.

        Returns
        -------
        int
            the value of the `FW_VERSION_L` register.
        """
        address = CommonRegisters.FIRMWARE_VERSION_L

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_device_name(self) -> str:
        """
        Reads the value stored in the `DEVICE_NAME` register.

        Returns
        -------
        int
            the value of the `DEVICE_NAME` register.
        """
        address = CommonRegisters.DEVICE_NAME

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

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

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        if reply.is_error:
            return 0

        return reply.payload

    def _read_clock_config(self) -> int:
        """
        Reads the value stored in the `CLOCK_CONFIG` register.

        Returns
        -------
        int
            the value of the `CLOCK_CONFIG` register.
        """
        address = CommonRegisters.CLOCK_CONFIG

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

    def _read_timestamp_offset(self) -> int:
        """
        Reads the value stored in the `TIMESTAMP_OFFSET` register.

        Returns
        -------
        int
            the value of the `TIMESTAMP_OFFSET` register.
        """
        address = CommonRegisters.TIMESTAMP_OFFSET

        reply: ReplyHarpMessage = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        return reply.payload

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
