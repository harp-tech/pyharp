from __future__ import annotations  # for type hints (PEP 563)

import logging
import queue
from enum import Enum
from io import BufferedWriter
from pathlib import Path
from typing import Optional

import serial
from harp.protocol import (
    ClockConfig,
    CommonRegisters,
    MessageType,
    OperationCtrl,
    OperationMode,
    PayloadType,
    ResetMode,
)
from harp.protocol.exceptions import HarpException, HarpTimeoutException
from harp.protocol.messages import HarpMessage
from harp.serial.harp_serial import HarpSerial


class TimeoutStrategy(Enum):
    """
    Strategy to handle timeouts when waiting for a reply from the device.

    Attributes
    ----------
    RAISE : str
        Raise HarpTimeoutException
    RETURN_NONE : str
        Return None
    LOG_AND_RAISE : str
        Log the timeout and raise HarpTimeoutException
    LOG_AND_NONE : str
        Log the timeout and return None
    """

    RAISE = "raise"  # Raise HarpTimeoutException
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
    HW_VERSION_H: int
    HW_VERSION_L: int
    ASSEMBLY_VERSION: int
    CORE_VERSION_H: int
    CORE_VERSION_L: int
    FIRMWARE_VERSION_H: int
    FIRMWARE_VERSION_L: int
    DEVICE_NAME: str
    SERIAL_NUMBER: int
    CLOCK_CONFIG: int
    TIMESTAMP_OFFSET: int

    _ser: HarpSerial
    _dump_file_path: Optional[Path]
    _dump_file: Optional[BufferedWriter] = None
    _timeout: float

    def __init__(
        self,
        serial_port: str,
        dump_file_path: Optional[str] = None,
        timeout: float = 1,
        timeout_strategy: TimeoutStrategy = TimeoutStrategy.RAISE,
    ):
        """
        Parameters
        ----------
        serial_port : str
            The serial port used to establish the connection with the Harp device. It must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port
        dump_file_path: str, optional
            The binary file to which all Harp messages will be written
        timeout: float, optional
            The timeout in seconds when waiting for a reply from the device
        timeout_strategy: TimeoutStrategy, optional
            The strategy to handle timeouts when waiting for a reply from the device
        """
        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._serial_port = serial_port
        self._dump_file_path = None
        if dump_file_path is not None:
            self._dump_file_path = Path() / dump_file_path
        self._timeout = timeout
        self._timeout_strategy = timeout_strategy

        # Connect to the Harp device and load the data stored in the device's common registers
        self.connect()
        self.load()

    def load(self) -> None:
        """
        Loads the data stored in the device's common registers.
        """
        self.WHO_AM_I = self._read_who_am_i()
        self.HW_VERSION_H = self._read_hw_version_h()
        self.HW_VERSION_L = self._read_hw_version_l()
        self.ASSEMBLY_VERSION = self._read_assembly_version()
        self.CORE_VERSION_H = self._read_core_version_h()
        self.CORE_VERSION_L = self._read_core_version_l()
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
        print(f"* Who am I: ({self.WHO_AM_I})")
        print(f"* HW version: {self.HW_VERSION_H}.{self.HW_VERSION_L}")
        print(f"* Assembly version: {self.ASSEMBLY_VERSION}")
        print(f"* HARP version: {self.CORE_VERSION_H}.{self.CORE_VERSION_L}")
        print(
            f"* Firmware version: {self.FIRMWARE_VERSION_H}.{self.FIRMWARE_VERSION_L}"
        )
        print(f"* Device name: {self.DEVICE_NAME}")
        print(f"* Serial number: {self.SERIAL_NUMBER}")
        print(f"* Mode: {self._read_device_mode().name}")

    def connect(self) -> None:
        """
        Connects to the Harp device.
        """
        self._ser = HarpSerial(
            self._serial_port,
            baudrate=1000000,
            timeout=self._timeout,
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
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))
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
        reg_value = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reg_value is None:
            return []

        reg_value = reg_value.payload

        # Assert DUMP bit
        reg_value |= OperationCtrl.DUMP
        self.send(HarpMessage(MessageType.WRITE, PayloadType.U8, address, reg_value))

        # Receive the contents of all registers as Harp Read Reply Messages
        replies = []
        while True:
            msg = self._read()
            if msg is not None:
                replies.append(msg)
            else:
                break
        return replies

    def read_operation_ctrl(self):
        """
        Reads the OPERATION_CTRL register of the device.

        Returns
        -------
        HarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        # create dict with complete byte and then decode each bit according to the OperationCtrl entries
        if reply is not None:
            reg_value = reply.payload
            result = {
                "REG_VALUE": reply.payload,
                "OP_MODE": OperationMode(reg_value & OperationCtrl.OP_MODE),
                "DUMP": bool(reg_value & OperationCtrl.DUMP),
                "MUTE_RPL": bool(reg_value & OperationCtrl.MUTE_RPL),
                "VISUALEN": bool(reg_value & OperationCtrl.VISUALEN),
                "OPLEDEN": bool(reg_value & OperationCtrl.OPLEDEN),
                "ALIVE_EN": bool(reg_value & OperationCtrl.ALIVE_EN),
            }
            return result

    def write_operation_ctrl(
        self,
        mode: Optional[OperationMode] = None,
        mute_rpl: Optional[bool] = None,
        visual_en: Optional[bool] = None,
        op_led_en: Optional[bool] = None,
        alive_en: Optional[bool] = None,
    ) -> HarpMessage | None:
        """
        Writes the OPERATION_CTRL register of the device.

        Parameters
        ----------
        mode : OperationMode, optional
            The new operation mode value
        mute_rpl : bool, optional
            If True, the Replies to all the Commands are muted
        visual_en : bool, optional
            If True, enables the status led
        op_led_en : bool, optional
            If True, enables the operation LED
        alive_en : bool, optional
            If True, enables the ALIVE_EN bit
        Returns
        -------
        HarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reply is None:
            return reply

        reg_value = reply.payload

        if mode is not None:
            # Clear old operation mode
            reg_value &= ~OperationCtrl.OP_MODE
            # Set new operation mode
            reg_value |= mode

        if mute_rpl is not None:
            if mute_rpl:
                reg_value |= OperationCtrl.MUTE_RPL
            else:
                reg_value &= ~OperationCtrl.MUTE_RPL

        if visual_en is not None:
            if visual_en:
                reg_value |= OperationCtrl.VISUALEN
            else:
                reg_value &= ~OperationCtrl.VISUALEN

        if op_led_en is not None:
            if op_led_en:
                reg_value |= OperationCtrl.OPLEDEN
            else:
                reg_value &= ~OperationCtrl.OPLEDEN

        if alive_en is not None:
            if alive_en:
                reg_value |= OperationCtrl.ALIVE_EN
            else:
                reg_value &= ~OperationCtrl.ALIVE_EN

        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, reg_value)
        )

        return reply

    def set_mode(self, mode: OperationMode) -> HarpMessage | None:
        """
        Sets the operation mode of the device.

        Parameters
        ----------
        mode : DeviceMode
            The new device mode value

        Returns
        -------
        HarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.OPERATION_CTRL

        # Read register first
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reply is None:
            return reply

        reg_value = reply.payload

        # Clear old operation mode
        reg_value &= ~OperationCtrl.OP_MODE

        # Set new operation mode
        reg_value |= mode
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, reg_value)
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
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reply is None:
            return False

        reg_value = reply.payload

        if enable:
            reg_value |= OperationCtrl.ALIVE_EN
        else:
            reg_value &= ~OperationCtrl.ALIVE_EN

        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, reg_value)
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
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reply is None:
            return False

        reg_value = reply.payload

        if enable:
            reg_value |= OperationCtrl.OPLEDEN
        else:
            reg_value &= ~OperationCtrl.OPLEDEN

        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, reg_value)
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
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reply is None:
            return False

        reg_value = reply.payload

        if enable:
            reg_value |= OperationCtrl.VISUALEN
        else:
            reg_value &= ~OperationCtrl.VISUALEN

        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, reg_value)
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
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reply is None:
            return False

        reg_value = reply.payload

        if enable:
            reg_value |= OperationCtrl.MUTE_RPL
        else:
            reg_value &= ~OperationCtrl.MUTE_RPL

        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, reg_value)
        )

        return reply is not None

    def reset_device(
        self, reset_mode: ResetMode = ResetMode.RST_DEF
    ) -> HarpMessage | None:
        """
        Resets the device and reboots with all the registers with the default values. Beware that the EEPROM will be erased. More information on the reset device register can be found [here](https://harp-tech.org/protocol/Device.html#r_reset_dev-u8--reset-device-and-save-non-volatile-registers).

        Returns
        -------
        HarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.RESET_DEV
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, reset_mode)
        )

        return reply

    def set_clock_config(self, clock_config: ClockConfig) -> HarpMessage | None:
        """
        Sets the clock configuration of the device.

        Parameters
        ----------
        clock_config : ClockConfig
            The clock configuration value

        Returns
        -------
        HarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.CLOCK_CONFIG
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, clock_config)
        )

        return reply

    def set_timestamp_offset(self, timestamp_offset: int) -> HarpMessage | None:
        """
        When the value of this register is above 0 (zero), the device's timestamp will be offset by this amount. The register is sensitive to 500 microsecond increments. This register is non-volatile.

        Parameters
        ----------
        timestamp_offset : int
            The timestamp offset value

        Returns
        -------
        HarpMessage
            The reply to the Harp message
        """
        address = CommonRegisters.TIMESTAMP_OFFSET
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, timestamp_offset)
        )

        return reply

    def send(
        self,
        message: HarpMessage,
        *,
        expect_reply: bool = True,
        timeout_strategy: TimeoutStrategy | None = None,
    ) -> HarpMessage | None:
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
        HarpMessage | None
            Reply (or None when allowed by the timeout strategy or expect_reply=False)

        Raises
        -------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        self._ser.write(message.frame)

        if not expect_reply:
            return None

        strategy = timeout_strategy or self._timeout_strategy

        try:
            reply = self._read()
        except TimeoutError:
            hte = HarpTimeoutException(self._timeout, message)
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

    def _read(self) -> HarpMessage:
        """
        Reads an incoming serial message in a blocking way.

        Returns
        -------
        HarpMessage
            The incoming Harp message in case it exists

        Raises
        -------
        TimeoutError
            If no reply is received within the timeout period
        """
        try:
            return self._ser.msg_q.get(block=True, timeout=self._timeout)
        except queue.Empty:
            raise TimeoutError("No reply received within the timeout period.")

    def _dump_reply(self, reply: bytearray):
        """
        Dumps the reply to a Harp message in the dump file in case it exists.
        """
        if self._dump_file:
            self._dump_file.write(reply)

    def get_events(self) -> list[HarpMessage]:
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
                msg = self._ser.event_q.get(timeout=False)
                self._dump_reply(msg.frame)
                msgs.append(msg)
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

    def read_u8(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type U8.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        return reply

    def read_s8(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type S8.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.S8, address))

        return reply

    def read_u16(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type U16.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U16, address))

        return reply

    def read_s16(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type S16.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.S16, address))

        return reply

    def read_u32(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type U32.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U32, address))

        return reply

    def read_s32(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type S32.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.S32, address))

        return reply

    def read_u64(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type U64.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U64, address))

        return reply

    def read_s64(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type S64.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.S64, address))

        return reply

    def read_float(self, address: int) -> HarpMessage | None:
        """
        Reads the value of a register of type Float.

        Parameters
        ----------
        address : int
            The register to be read

        Returns
        -------
        HarpMessage
            The reply to the Harp message that will contain the value read from the register

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(HarpMessage(MessageType.READ, PayloadType.FLOAT, address))

        return reply

    def write_u8(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U8, address, value)
        )

        return reply

    def write_s8(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.S8, address, value)
        )

        return reply

    def write_u16(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U16, address, value)
        )

        return reply

    def write_s16(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.S16, address, value)
        )

        return reply

    def write_u32(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U32, address, value)
        )

        return reply

    def write_s32(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.S32, address, value)
        )

        return reply

    def write_u64(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.U64, address, value)
        )

        return reply

    def write_s64(self, address: int, value: int | list[int]) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.S64, address, value)
        )

        return reply

    def write_float(
        self, address: int, value: float | list[float]
    ) -> HarpMessage | None:
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
        HarpMessage
            The reply to the Harp message

        Raises
        ------
        HarpTimeoutException
            If no reply is received and the effective strategy requires raising
        """
        reply = self.send(
            HarpMessage(MessageType.WRITE, PayloadType.FLOAT, address, value)
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

        # Attempt to read the WHO_AM_I register to verify if the device is a Harp device
        error_msg = "This is not a Harp device."
        try:
            reply = self.send(HarpMessage(MessageType.READ, PayloadType.U16, address))
        except HarpTimeoutException:
            raise HarpException(error_msg)

        if reply is None:
            raise HarpException(error_msg)

        return reply.payload

    def _read_hw_version_h(self) -> int:
        """
        Reads the value stored in the `HW_VERSION_H` register.

        Returns
        -------
        int
            The value of the `HW_VERSION_H` register
        """
        address = CommonRegisters.HW_VERSION_H

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        return reply.payload

    def _read_core_version_h(self) -> int:
        """
        Reads the value stored in the `CORE_VERSION_H` register.

        Returns
        -------
        int
            The value of the `CORE_VERSION_H` register
        """
        address = CommonRegisters.CORE_VERSION_H

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        return reply.payload

    def _read_core_version_l(self) -> int:
        """
        Reads the value stored in the `CORE_VERSION_L` register.

        Returns
        -------
        int
            The value of the `CORE_VERSION_L` register
        """
        address = CommonRegisters.CORE_VERSION_L

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

        if reply is not None and reply.is_error:
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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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

        reply = self.send(HarpMessage(MessageType.READ, PayloadType.U8, address))

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
