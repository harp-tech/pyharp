from __future__ import annotations  # enable subscriptable type hints for lists.

import logging
import queue
from enum import Enum
from io import BufferedWriter
from pathlib import Path
from typing import Optional

from harp.protocol import (
    ClockConfig,
    CommonRegisters,
    MessageType,
    OperationCtrl,
    OperationMode,
    PayloadType,
    ResetMode,
)
from harp.protocol.device_names import device_names
from harp.protocol.exceptions import HarpTimeoutError
from harp.protocol.messages import HarpMessage, ReplyHarpMessage
from harp.serial.harp_serial import HarpSerial

import serial


class TimeoutStrategy(Enum):
    RAISE = "raise"  # Raise HarpTimeoutError
    RETURN_NONE = "return_none"  # Return None
    LOG_AND_RAISE = "log_and_raise"
    LOG_AND_NONE = "log_and_none"


class Device:
    """
    The `Device` class provides the interface for interacting with Harp devices. This implementation of the Harp device was based on the official documentation available on the [harp-tech website](https://harp-tech.org/protocol/Device.html).

    Attributes
    ----------
    WHO_AM_I : int
        The device ID number. A list of devices can be found [here](https://github.com/harp-tech/protocol/blob/main/whoami.md)
    DEFAULT_DEVICE_NAME : str
        The device name, i.e. "Behavior". This name is derived by cross-referencing the `WHO_AM_I` identifier with the corresponding device name in the `device_names` dictionary
    HW_VERSION_H : int
        The major hardware version
    HW_VERSION_L : int
        The minor hardware version
    ASSEMBLY_VERSION : int
        The version of the assembled components
    HARP_VERSION_H : int
        The major Harp core version
    HARP_VERSION_L : int
        The minor Harp core version
    FIRMWARE_VERSION_H : int
        The major firmware version
    FIRMWARE_VERSION_L : int
        The minor firmware version
    DEVICE_NAME : str
        The device name stored in the Harp device
    SERIAL_NUMBER : int, optional
        The serial number of the device
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
    _dump_file_path: Optional[Path]
    _dump_file: Optional[BufferedWriter] = None
    _read_timeout_s: float

    _TIMEOUT_S: float = 1.0

    def __init__(
        self,
        serial_port: str,
        dump_file_path: Optional[str] = None,
        read_timeout_s: float = 1,
        timeout_strategy: TimeoutStrategy = TimeoutStrategy.RAISE,
    ):
        """
        Parameters
        ----------
        serial_port : str
            The serial port used to establish the connection with the Harp device. It must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port
        dump_file_path: str, optional
            The binary file to which all Harp messages will be written
        read_timeout_s: float, optional
            _TODO_
        """
        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._serial_port = serial_port
        self._dump_file_path = None
        if dump_file_path is not None:
            self._dump_file_path = Path() / dump_file_path
        self._read_timeout_s = read_timeout_s
        self._timeout_strategy = timeout_strategy

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
            The current device mode
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
            The list containing the reply Harp messages for all the device's registers
        """
        address = CommonRegisters.OPERATION_CTRL
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        if reg_value is None:
            return []

        reg_value = reg_value.payload

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

    def set_mode(self, mode: OperationMode) -> ReplyHarpMessage | None:
        """
        Sets the operation mode of the device.

        Parameters
        ----------
        mode : DeviceMode
            The new device mode value

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        if reg_value is None:
            return reg_value

        reg_value = reg_value.payload

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
            If True, enables the ALIVE_EN bit. If False, disables it

        Returns
        -------
        bool
            True if the operation was successful, False otherwise
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        if reg_value is None:
            return False

        reg_value = reg_value.payload

        if enable:
            reg_value |= OperationCtrl.ALIVE_EN
        else:
            reg_value &= ~OperationCtrl.ALIVE_EN

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        if reply is None:
            return False

        return reply is not None

    def op_led_en(self, enable: bool) -> bool:
        """
        Sets the operation LED of the device.

        Parameters
        ----------
        enable : bool
            If True, enables the operation LED. If False, disables it

        Returns
        -------
        bool
            True if the operation was successful, False otherwise
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        if reg_value is None:
            return False

        reg_value = reg_value.payload

        if enable:
            reg_value |= OperationCtrl.OPLEDEN
        else:
            reg_value &= ~OperationCtrl.OPLEDEN

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply is not None

    def visual_en(self, enable: bool) -> bool:
        """
        Sets the status led of the device.

        Parameters
        ----------
        enable : bool
            If True, enables the status led. If False, disables it

        Returns
        -------
        bool
            True if the operation was successful, False otherwise
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        if reg_value is None:
            return False

        reg_value = reg_value.payload

        if enable:
            reg_value |= OperationCtrl.VISUALEN
        else:
            reg_value &= ~OperationCtrl.VISUALEN

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply is not None

    def mute_reply(self, enable: bool) -> bool:
        """
        Sets the MUTE_REPLY bit of the device.

        Parameters
        ----------
        enable : bool
            If True, the Replies to all the Commands are muted. If False, un-mutes them

        Returns
        -------
        bool
            True if the operation was successful, False otherwise
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reg_value = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U8)
        )

        if reg_value is None:
            return False

        reg_value = reg_value.payload

        if enable:
            reg_value |= OperationCtrl.MUTE_RPL
        else:
            reg_value &= ~OperationCtrl.MUTE_RPL

        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reg_value)
        )

        return reply is not None

    def reset_device(
        self, reset_mode: ResetMode = ResetMode.RST_DEF
    ) -> ReplyHarpMessage | None:
        """
        Resets the device and reboots with all the registers with the default values. Beware that the EEPROM will be erased. More information on the reset device register can be found [here](https://harp-tech.org/protocol/Device.html#r_reset_dev-u8--reset-device-and-save-non-volatile-registers).

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.RESET_DEV
        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, reset_mode)
        )

        return reply

    def set_clock_config(self, clock_config: ClockConfig) -> ReplyHarpMessage | None:
        """
        Sets the clock configuration of the device.

        Parameters
        ----------
        clock_config : ClockConfig
            The clock configuration value

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.CLOCK_CONFIG
        reply = self.send(
            HarpMessage.create(MessageType.WRITE, address, PayloadType.U8, clock_config)
        )

        return reply

    def set_timestamp_offset(self, timestamp_offset: int) -> ReplyHarpMessage | None:
        """
        When the value of this register is above 0 (zero), the device's timestamp will be offset by this amount. The register is sensitive to 500 microsecond increments. This register is non-volatile.

        Parameters
        ----------
        timestamp_offset : int
            The timestamp offset value

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.TIMESTAMP_OFFSET
        reply = self.send(
            HarpMessage.create(
                MessageType.WRITE, address, PayloadType.U8, timestamp_offset
            )
        )

        return reply

    def send(
        self,
        message: HarpMessage,
        *,
        expect_reply: bool = True,
        timeout_strategy: TimeoutStrategy | None = None,
    ) -> ReplyHarpMessage | None:
        """
        Sends a Harp message and (optionally) waits for a reply.

        Parameters
        ----------
        message : HarpMessage
            The HarpMessage to be sent to the device
        expect_reply : bool, optional
            If False, do not wait for a reply (fire-and-forget)
        timeout_strategy : TimeoutStrategy | None
            Override the device-level timeout strategy for this call

        Returns
        -------
        ReplyHarpMessage | None
            Reply (or None when allowed by the timeout strategy or expect_reply=False)

        Raises
        -------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        self._ser.write(message.frame)

        if not expect_reply:
            return None

        strategy = timeout_strategy or self._timeout_strategy

        try:
            reply = self._read()
        except TimeoutError:
            hte = HarpTimeoutError(self._read_timeout_s)
            if strategy in (
                TimeoutStrategy.LOG_AND_RAISE,
                TimeoutStrategy.LOG_AND_NONE,
            ):
                self.log.warning(str(hte))
            if strategy in (TimeoutStrategy.RAISE, TimeoutStrategy.LOG_AND_RAISE):
                raise hte
            return None

        self._dump_reply(reply.frame)
        return reply

    def _read(self) -> ReplyHarpMessage:
        """
        Reads an incoming serial message in a blocking way.

        Returns
        -------
        ReplyHarpMessage
            The incoming Harp message in case it exists

        Raises
        -------
        TimeoutError
            If no reply is received within the timeout period
        """
        try:
            return self._ser.msg_q.get(block=True, timeout=self._read_timeout_s)
        except queue.Empty:
            raise TimeoutError("No reply received within the timeout period.")

    def _dump_reply(self, reply: bytearray):
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
            The list containing every Harp event message that were on the queue
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
            The number of events in the event queue
        """
        return self._ser.event_q.qsize()

    def read_u8(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type U8.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U8,
            )
        )

        return reply

    def read_s8(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type S8.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S8,
            )
        )

        return reply

    def read_u16(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type U16.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U16,
            )
        )

        return reply

    def read_s16(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type S16.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S16,
            )
        )

        return reply

    def read_u32(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type U32.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U32,
            )
        )

        return reply

    def read_s32(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type S32.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S32,
            )
        )

        return reply

    def read_u64(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type U64.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.U64,
            )
        )

        return reply

    def read_s64(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type S64.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.S64,
            )
        )

        return reply

    def read_float(self, address: int) -> ReplyHarpMessage | None:
        """
        Reads the value of a register of type Float.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.READ,
                address=address,
                payload_type=PayloadType.Float,
            )
        )

        return reply

    def write_u8(self, address: int, value: int | list[int]) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type U8.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U8,
                value=value,
            )
        )

        return reply

    def write_s8(self, address: int, value: int | list[int]) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type S8.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S8,
                value=value,
            )
        )

        return reply

    def write_u16(
        self, address: int, value: int | list[int]
    ) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type U16.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U16,
                value=value,
            )
        )

        return reply

    def write_s16(
        self, address: int, value: int | list[int]
    ) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type S16.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S16,
                value=value,
            )
        )

        return reply

    def write_u32(
        self, address: int, value: int | list[int]
    ) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type U32.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U32,
                value=value,
            )
        )

        return reply

    def write_s32(
        self, address: int, value: int | list[int]
    ) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type S32.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S32,
                value=value,
            )
        )

        return reply

    def write_u64(
        self, address: int, value: int | list[int]
    ) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type U64.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.U64,
                value=value,
            )
        )

        return reply

    def write_s64(
        self, address: int, value: int | list[int]
    ) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type S64.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.S64,
                value=value,
            )
        )

        return reply

    def write_float(
        self, address: int, value: float | list[float]
    ) -> ReplyHarpMessage | None:
        """
        Writes the value of a register of type Float.

        Parameters
        ----------
        address : int
            The register to be written on
        value: int | list[int]
            The value to be written to the register

        Returns
        -------
        ReplyHarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutError
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage.create(
                message_type=MessageType.WRITE,
                address=address,
                payload_type=PayloadType.Float,
                value=value,
            )
        )

        return reply

    def _read_who_am_i(self) -> int:
        """
        Reads the value stored in the `WHO_AM_I` register.

        Returns
        -------
        int
            The value of the `WHO_AM_I` register
        """
        address = CommonRegisters.WHO_AM_I

        reply = self.send(
            HarpMessage.create(MessageType.READ, address, PayloadType.U16)
        )

        return reply.payload

    def _read_default_device_name(self) -> str:
        """
        Returns the `DEFAULT_DEVICE_NAME` by cross-referencing the `WHO_AM_I` with the corresponding device name in the `device_names` dictionary.

        Returns
        -------
        str
            The default device name
        """
        return device_names.get(self.WHO_AM_I, "Unknown device")

    def _read_hw_version_h(self) -> int:
        """
        Reads the value stored in the `HW_VERSION_H` register.

        Returns
        -------
        int
            The value of the `HW_VERSION_H` register
        """
        address = CommonRegisters.HW_VERSION_H

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_hw_version_l(self) -> int:
        """
        Reads the value stored in the `HW_VERSION_L` register.

        Returns
        -------
        int
            The value of the `HW_VERSION_L` register
        """
        address = CommonRegisters.HW_VERSION_L

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_assembly_version(self) -> int:
        """
        Reads the value stored in the `ASSEMBLY_VERSION` register.

        Returns
        -------
        int
            The value of the `ASSEMBLY_VERSION` register
        """
        address = CommonRegisters.ASSEMBLY_VERSION

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_harp_version_h(self) -> int:
        """
        Reads the value stored in the `HARP_VERSION_H` register.

        Returns
        -------
        int
            The value of the `HARP_VERSION_H` register
        """
        address = CommonRegisters.HARP_VERSION_H

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_harp_version_l(self) -> int:
        """
        Reads the value stored in the `HARP_VERSION_L` register.

        Returns
        -------
        int
            The value of the `HARP_VERSION_L` register
        """
        address = CommonRegisters.HARP_VERSION_L

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_fw_version_h(self) -> int:
        """
        Reads the value stored in the `FW_VERSION_H` register.

        Returns
        -------
        int
            The value of the `FW_VERSION_H` register
        """
        address = CommonRegisters.FIRMWARE_VERSION_H

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_fw_version_l(self) -> int:
        """
        Reads the value stored in the `FW_VERSION_L` register.

        Returns
        -------
        int
            The value of the `FW_VERSION_L` register
        """
        address = CommonRegisters.FIRMWARE_VERSION_L

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_device_name(self) -> str:
        """
        Reads the value stored in the `DEVICE_NAME` register.

        Returns
        -------
        int
            The value of the `DEVICE_NAME` register
        """
        address = CommonRegisters.DEVICE_NAME

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload_as_string()

    def _read_serial_number(self) -> int:
        """
        Reads the value stored in the `SERIAL_NUMBER` register.

        Returns
        -------
        int
            The value of the `SERIAL_NUMBER` register
        """
        address = CommonRegisters.SERIAL_NUMBER

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        if reply.is_error:
            return 0

        return reply.payload

    def _read_clock_config(self) -> int:
        """
        Reads the value stored in the `CLOCK_CONFIG` register.

        Returns
        -------
        int
            The value of the `CLOCK_CONFIG` register
        """
        address = CommonRegisters.CLOCK_CONFIG

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

        return reply.payload

    def _read_timestamp_offset(self) -> int:
        """
        Reads the value stored in the `TIMESTAMP_OFFSET` register.

        Returns
        -------
        int
            The value of the `TIMESTAMP_OFFSET` register
        """
        address = CommonRegisters.TIMESTAMP_OFFSET

        reply = self.send(HarpMessage.create(MessageType.READ, address, PayloadType.U8))

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
