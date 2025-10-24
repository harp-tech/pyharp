from __future__ import annotations  # for type hints (PEP 563)

import struct
from typing import Optional, Union

from harp.protocol import MessageType, PayloadType


class HarpMessage:
    """
    The `HarpMessage` class implements the Harp message as described in the [protocol](https://harp-tech.org/protocol/BinaryProtocol-8bit.html).

    Attributes
    ----------
    frame : bytearray
        The bytearray containing the whole Harp message
    message_type : MessageType
        The message type
    length : int
        The length parameter of the Harp message
    address : int
        The address of the register to which the Harp message refers to
    port : int
        Indicates the origin or destination of the Harp message in case the device is a hub of Harp devices. The value 255 points to the device itself (default value).
    payload_type : PayloadType
        The payload type
    checksum : int
        The sum of all bytes contained in the Harp message
    """

    DEFAULT_PORT: int = 255
    BASE_LENGTH: int = 4
    _frame: bytearray = bytearray()
    _port: int = DEFAULT_PORT
    _timestamp: Optional[float] = None
    _raw_payload: bytearray = bytearray()

    def __init__(
        self,
        message_type: MessageType,
        payload_type: PayloadType,
        address: int,
        value: Optional[int | float | list[int] | list[float]] = None,
    ):
        """
        Parameters
        ----------
        message_type : MessageType
            The message type.
        payload_type : PayloadType
            The payload type.
        address : int
            The address of the register that the message will interact with.
        value: int | list[int] | float | list[float], optional
            The payload of the message. If message_type == MessageType.WRITE, the value cannot be None
        """
        self._frame = bytearray()
        payload = bytearray()

        if value is not None:
            if isinstance(value, int) or isinstance(value, float):
                values = [value]
            else:
                values = value

            for val in values:
                if isinstance(val, float):
                    payload += struct.pack("<f", val)
                else:
                    payload += val.to_bytes(
                        payload_type.type_size(),
                        byteorder="little",
                        signed=payload_type.is_signed(),
                    )

        self._frame.append(message_type)
        self._frame.append(self.BASE_LENGTH + len(payload))
        self._frame.append(address)
        self._frame.append(self._port)
        self._frame.append(payload_type)

        if value is not None:
            self._frame += payload
            if self.payload_type.has_timestamp():
                self._raw_payload = self._frame[11:-1]
            else:
                self._raw_payload = self._frame[5:-1]

        self._frame.append(self.calculate_checksum())

    def calculate_checksum(self) -> int:
        """
        Calculates the checksum of the Harp message.

        Returns
        -------
        int
            The value of the checksum
        """
        checksum: int = 0
        for i in self.frame:
            checksum += i
        return checksum & 255

    @property
    def frame(self) -> bytearray:
        """
        The bytearray containing the whole Harp message.

        Returns
        -------
        bytearray
            The bytearray containing the whole Harp message
        """
        return self._frame

    @property
    def message_type(self) -> MessageType:
        """
        The message type.

        Returns
        -------
        MessageType
            The message type
        """
        return MessageType(self._frame[0])

    @property
    def length(self) -> int:
        """
        The length parameter of the Harp message.

        Returns
        -------
        int
            The length parameter of the Harp message
        """
        return self._frame[1]

    @property
    def address(self) -> int:
        """
        The address of the register to which the Harp message refers to.

        Returns
        -------
        int
            The address of the register to which the Harp message refers to
        """
        return self._frame[2]

    @property
    def port(self) -> int:
        """
        Indicates the origin or destination of the Harp message in case the device is a hub of Harp devices. The value 255 points to the device itself (default value).

        Returns
        -------
        int
            The port value
        """
        return self._frame[3]

    @port.setter
    def port(self, value: int) -> None:
        """
        Sets the port value.

        Parameters
        ----------
        value : int
            The port value to set
        """
        self._port = value

    @property
    def payload_type(self) -> PayloadType:
        """
        The payload type.

        Returns
        -------
        PayloadType
            The payload type
        """
        return PayloadType(self._frame[4])

    @property
    def timestamp(self) -> float | None:
        return self._timestamp

    @property
    def payload(self) -> Union[int, list[int], bytearray, float, list[float]]:
        """
        The payload sent in the write Harp message.

        Returns
        -------
        Union[int, list[int]]
            The payload sent in the write Harp message
        """
        payload_start = self.BASE_LENGTH
        if self.payload_type.has_timestamp():
            payload_start += 6

        payload_index = payload_start + 1

        # length is payload_start + payload type size
        pt = self.payload_type
        if pt == PayloadType.U8 or pt == PayloadType.TIMESTAMPED_U8:
            if self.length == payload_start + 1:
                return self._frame[payload_index]
            else:  # array case
                return [
                    int.from_bytes([self._frame[i]], byteorder="little")
                    for i in range(payload_index, self.length + 1)
                ]

        elif pt == PayloadType.S8 or pt == PayloadType.TIMESTAMPED_S8:
            if self.length == payload_start + 1:
                return int.from_bytes(
                    [self._frame[payload_index]], byteorder="little", signed=True
                )
            else:  # array case
                return [
                    int.from_bytes(
                        [self._frame[i]],
                        byteorder="little",
                        signed=True,
                    )
                    for i in range(payload_index, self.length + 1)
                ]

        elif pt == PayloadType.U16 or pt == PayloadType.TIMESTAMPED_U16:
            if self.length == payload_start + 2:
                return int.from_bytes(
                    self._frame[payload_index : payload_index + 2],
                    byteorder="little",
                    signed=False,
                )
            else:  # array case
                return [
                    int.from_bytes(
                        self._frame[i : i + 2],
                        byteorder="little",
                        signed=False,
                    )
                    for i in range(payload_index, self.length + 1, 2)
                ]

        elif pt == PayloadType.S16 or pt == PayloadType.TIMESTAMPED_S16:
            if self.length == payload_start + 2:
                return int.from_bytes(
                    self._frame[payload_index : payload_index + 2],
                    byteorder="little",
                    signed=True,
                )
            else:
                return [
                    int.from_bytes(
                        self._frame[i : i + 2],
                        byteorder="little",
                        signed=True,
                    )
                    for i in range(payload_index, self.length + 1, 2)
                ]

        elif pt == PayloadType.U32 or pt == PayloadType.TIMESTAMPED_U32:
            if self.length == payload_start + 4:
                return int.from_bytes(
                    self._frame[payload_index : payload_index + 4],
                    byteorder="little",
                    signed=False,
                )
            else:
                return [
                    int.from_bytes(
                        self._frame[i : i + 4],
                        byteorder="little",
                        signed=False,
                    )
                    for i in range(payload_index, self.length + 1, 4)
                ]

        elif pt == PayloadType.S32 or pt == PayloadType.TIMESTAMPED_S32:
            if self.length == payload_start + 4:
                return int.from_bytes(
                    self._frame[payload_index : payload_index + 4],
                    byteorder="little",
                    signed=True,
                )
            else:
                return [
                    int.from_bytes(
                        self._frame[i : i + 4],
                        byteorder="little",
                        signed=True,
                    )
                    for i in range(payload_index, self.length + 1, 4)
                ]

        elif pt == PayloadType.U64 or pt == PayloadType.TIMESTAMPED_U64:
            if self.length == payload_start + 8:
                return int.from_bytes(
                    self._frame[payload_index : payload_index + 8],
                    byteorder="little",
                    signed=False,
                )
            else:
                return [
                    int.from_bytes(
                        self._frame[i : i + 8],
                        byteorder="little",
                        signed=False,
                    )
                    for i in range(payload_index, self.length + 1, 8)
                ]

        elif pt == PayloadType.S64 or pt == PayloadType.TIMESTAMPED_S64:
            if self.length == payload_start + 8:
                return int.from_bytes(
                    self._frame[payload_index : payload_index + 8],
                    byteorder="little",
                    signed=True,
                )
            else:
                return [
                    int.from_bytes(
                        self._frame[i : i + 8],
                        byteorder="little",
                        signed=True,
                    )
                    for i in range(payload_index, self.length + 1, 8)
                ]

        elif pt == PayloadType.FLOAT or pt == PayloadType.TIMESTAMPED_FLOAT:
            if self.length == payload_start + 4:
                return struct.unpack(
                    "<f", self._frame[payload_index : payload_index + 4]
                )[0]
            else:
                return [
                    struct.unpack("<f", self._frame[i : i + 4])[0]
                    for i in range(payload_index, self.length + 1, 4)
                ]

        else:
            # For any other payload type, return the raw payload, excluding checksum
            return self._frame[payload_index:-1]

    @property
    def checksum(self) -> int:
        """
        The sum of all bytes contained in the Harp message.

        Returns
        -------
        int
            The sum of all bytes contained in the Harp message
        """
        return self._frame[-1]

    @property
    def is_error(self) -> bool:
        """
        Indicates if this HarpMessage is an error message or not.

        Returns
        -------
        bool
            Returns True if this HarpMessage is an error message, False otherwise.
        """
        return self.message_type.is_error()

    def payload_as_string(self) -> str:
        """
        Returns the payload as a str.

        Returns
        -------
        str
            The payload parsed as a str
        """
        return self._raw_payload.decode("utf-8").rstrip("\x00")

    @staticmethod
    def parse(frame: bytearray) -> HarpMessage:
        """
        Parses a bytearray to a (reply) Harp message.

        Parameters
        ----------
        frame : bytearray
            The bytearray will be parsed into a (reply) Harp message

        Returns
        -------
        HarpMessage
            The Harp message object parsed from the original bytearray
        """
        message = HarpMessage(MessageType(frame[0]), PayloadType(frame[4]), frame[2])

        message._frame = frame

        # assign timestamp if exists
        if message.payload_type.has_timestamp():
            message._raw_payload = frame[11:-1]
            message._timestamp = (
                int.from_bytes(frame[5:9], byteorder="little", signed=False)
                + int.from_bytes(frame[9:11], byteorder="little", signed=False) * 32e-6
            )
        else:
            message._raw_payload = frame[5:-1]
            message._timestamp = None

        return message

    def __repr__(self) -> str:
        """
        Prints debug representation of the reply message.

        Returns
        -------
        str
            The debug representation of the reply message
        """
        return self.__str__() + f"\r\nRaw Frame: {self.frame}"

    def __str__(self) -> str:
        """
        Prints friendly representation of a Harp message.

        Returns
        -------
        str
            The representation of the Harp message
        """
        payload_str = ""
        format_str = ""
        if self.payload_type in [PayloadType.FLOAT, PayloadType.TIMESTAMPED_FLOAT]:
            format_str = ".6f"
        else:
            bytes_per_word = self.payload_type & 0x07
            format_str = f"0{bytes_per_word}b"

        payload_str = "".join(
            f"{item:{format_str}} "
            for item in (
                self.payload if isinstance(self.payload, list) else [self.payload]
            )
        )

        # Check if the object has a 'timestamp' property and it's not None
        timestamp_line = ""
        if hasattr(self, "timestamp"):
            ts = getattr(self, "timestamp")
            if ts is not None:
                timestamp_line = f"Timestamp: {ts}\r\n"

        return (
            f"Type: {self.message_type.name}\r\n"
            + f"Length: {self.length}\r\n"
            + f"Address: {self.address}\r\n"
            + f"Port: {self.port}\r\n"
            + timestamp_line
            + f"Payload Type: {self.payload_type.name}\r\n"
            + f"Payload Length: {len(self.payload) if self.payload is list else 1}\r\n"
            + f"Payload: {payload_str}\r\n"
            + f"Checksum: {self.checksum}"
        )
