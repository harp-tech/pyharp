from __future__ import annotations  # for type hints (PEP 563)

import struct
from typing import List, Union

from pyharp import MessageType, PayloadType


class HarpMessage:
    """
    The `HarpMessage` class implements the Harp message as described in the [protocol](https://harp-tech.org/protocol/BinaryProtocol-8bit.html).

    Attributes
    ----------
    frame : bytearray
        the bytearray containing the whole Harp message
    message_type : MessageType
        the message type
    length : int
        the length parameter of the Harp message
    address : int
        the address of the register to which the Harp message refers to
    port : int
        indicates the origin or destination of the Harp message in case the device is a hub of Harp devices. The value 255 points to the device itself (default value).
    payload_type : PayloadType
        the payload type
    checksum : int
        the sum of all bytes contained in the Harp message
    """

    DEFAULT_PORT: int = 255
    BASE_LENGTH: int = 4
    _frame: bytearray

    def __init__(self):
        self._frame = bytearray()
        self._port = self.DEFAULT_PORT

    def calculate_checksum(self) -> int:
        """
        Calculates the checksum of the Harp message.

        Returns
        -------
        int
            the value of the checksum
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
            the bytearray containing the whole Harp message
        """
        return self._frame

    @property
    def message_type(self) -> MessageType:
        """
        The message type.

        Returns
        -------
        MessageType
            the message type
        """
        return MessageType(self._frame[0])

    @property
    def length(self) -> int:
        """
        The length parameter of the Harp message.

        Returns
        -------
        int
            the length parameter of the Harp message
        """
        return self._frame[1]

    @property
    def address(self) -> int:
        """
        The address of the register to which the Harp message refers to.

        Returns
        -------
        int
            the address of the register to which the Harp message refers to
        """
        return self._frame[2]

    @property
    def port(self) -> int:
        """
        Indicates the origin or destination of the Harp message in case the device is a hub of Harp devices. The value 255 points to the device itself (default value).

        Returns
        -------
        int
            the port value
        """
        return self._frame[3]

    @port.setter
    def port(self, value: int) -> None:
        """
        Sets the port value.

        Parameters
        ----------
        value : int
            the port value to set
        """
        self._port = value

    @property
    def payload_type(self) -> PayloadType:
        """
        The payload type.

        Returns
        -------
        PayloadType
            the payload type
        """
        return PayloadType(self._frame[4])

    @property
    def payload(self) -> Union[int, list[int]]:
        """
        The payload sent in the write Harp message.

        Returns
        -------
        Union[int, list[int]]
            the payload sent in the write Harp message
        """
        payload_start = self.BASE_LENGTH
        if self.payload_type & PayloadType.Timestamp:
            payload_start += 6

        payload_index = payload_start + 1

        # length is payload_start + payload type size
        match self.payload_type:
            case PayloadType.U8 | PayloadType.TimestampedU8:
                if self.length == payload_start + 1:
                    return self._frame[payload_index]
                else:  # array case
                    return [
                        int.from_bytes([self._frame[i]], byteorder="little")
                        for i in range(payload_index, self.length + 1)
                    ]

            case PayloadType.S8 | PayloadType.TimestampedS8:
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

            case PayloadType.U16 | PayloadType.TimestampedU16:
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

            case PayloadType.S16 | PayloadType.TimestampedS16:
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

            case PayloadType.U32 | PayloadType.TimestampedU32:
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

            case PayloadType.S32 | PayloadType.TimestampedS32:
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

            case PayloadType.U64 | PayloadType.TimestampedU64:
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

            case PayloadType.S64 | PayloadType.TimestampedS64:
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

            case PayloadType.Float | PayloadType.TimestampedFloat:
                if self.length == payload_start + 4:
                    return struct.unpack(
                        "<f", self._frame[payload_index : payload_index + 4]
                    )[0]
                else:
                    return [
                        struct.unpack("<f", self._frame[i : i + 4])[0]
                        for i in range(payload_index, self.length + 1, 4)
                    ]

            case _:
                # For any other payload type, return the raw payload, excluding checksum
                return self._frame[payload_index:-1]

    @property
    def checksum(self) -> int:
        """
        The sum of all bytes contained in the Harp message.

        Returns
        -------
        int
            the sum of all bytes contained in the Harp message
        """
        return self._frame[-1]

    @staticmethod
    def parse(frame: bytearray) -> ReplyHarpMessage:
        """
        Parses a bytearray to a (reply) Harp message.

        Parameters
        ----------
        frame : bytearray
            the bytearray will be parsed into a (reply) Harp message

        Returns
        -------
        ReplyHarpMessage
            the Harp message object parsed from the original bytearray
        """
        return ReplyHarpMessage(frame)

    @staticmethod
    def create(
        message_type: MessageType,
        address: int,
        payload_type: PayloadType,
        value: int | list[int] | float | list[float] = None,
    ) -> HarpMessage:
        """
        Creates a Harp message.

        Parameters
        ----------
        message_type : MessageType
            the message type. It can only be of type READ or WRITE
        address : int
            the address of the register that the message will interact with
        payload_type : PayloadType
            the payload type
        value: int | list[int] | float | list[float], optional
            the payload of the message. If message_type == MessageType.WRITE, the value cannot be None
        """
        if message_type == MessageType.READ:
            return ReadHarpMessage(payload_type, address)
        elif message_type == MessageType.WRITE and value is not None:
            return WriteHarpMessage(payload_type, address, value)
        elif message_type != MessageType.READ and message_type != MessageType.WRITE:
            raise Exception(
                "The only valid message types are MessageType.READ and MessageType.Write!"
            )
        else:
            raise Exception(
                "The value cannot be None is message type is equal to MessageType.WRITE!"
            )

    def __repr__(self) -> str:
        """
        Prints debug representation of the reply message.

        Returns
        -------
        str
            the debug representation of the reply message
        """
        return self.__str__() + f"\r\nRaw Frame: {self.frame}"

    def __str__(self) -> str:
        """
        Prints friendly representation of a Harp message.

        Returns
        -------
        str
            the representation of the Harp message
        """
        payload_str = ""
        format_str = ""
        if self.payload_type in [PayloadType.Float, PayloadType.TimestampedFloat]:
            format_str = ".6f"
        else:
            bytes_per_word = self.payload_type & 0x07
            format_str = f"0{bytes_per_word}b"

        payload_str = "".join(
            f"{item:{format_str}} "
            for item in (self.payload if self.payload is list else [self.payload])
        )

        return (
            f"Type: {self.message_type.name}\r\n"
            + f"Length: {self.length}\r\n"
            + f"Address: {self.address}\r\n"
            + f"Port: {self.port}\r\n"
            + f"Timestamp: {self.timestamp}\r\n"
            + f"Payload Type: {self.payload_type.name}\r\n"
            + f"Payload Length: {len(self.payload) if self.payload is list else 1}\r\n"
            + f"Payload: {payload_str}\r\n"
            + f"Checksum: {self.checksum}"
        )


class ReplyHarpMessage(HarpMessage):
    """
    A response message from a Harp device.

    Attributes
    ----------
    payload : Union[int, list[int]]
        the message payload formatted as the appropriate type
    timestamp : float
        the Harp timestamp at which the message was sent
    """

    def __init__(
        self,
        frame: bytearray,
    ):
        """
        Parameters
        ----------
        frame : bytearray
            the Harp message in bytearray format
        """

        self._frame = frame
        # Retrieve all content from 11 (where payload starts) until the checksum (not inclusive)
        self._raw_payload = frame[11:-1]

        # Assign timestamp after _payload since @properties all rely on self._payload.
        self._timestamp = (
            int.from_bytes(frame[5:9], byteorder="little", signed=False)
            + int.from_bytes(frame[9:11], byteorder="little", signed=False) * 32e-6
        )

        # Timestamp is junk if it's not present.
        if not (self.payload_type & PayloadType.Timestamp):
            self._timestamp = None

    @property
    def is_error(self) -> bool:
        """
        Indicates if this HarpMessage is an error message or not.

        Returns
        -------
        bool
            Returns True if this HarpMessage is an error message, False otherwise.
        """
        return self.message_type in [MessageType.READ_ERROR, MessageType.WRITE_ERROR]

    @property
    def timestamp(self) -> float:
        """
        The Harp timestamp at which the message was sent.

        Returns
        -------
        float
            the Harp timestamp at which the message was sent
        """
        return self._timestamp

    def payload_as_string(self) -> str:
        """
        Returns the payload as a str.

        Returns
        -------
        str
            the payload parsed as a str
        """
        return self._raw_payload.decode("utf-8").rstrip("\x00")


class ReadHarpMessage(HarpMessage):
    """
    A read Harp message sent to a Harp device.
    """

    MESSAGE_TYPE: int = MessageType.READ

    def __init__(self, payload_type: PayloadType, address: int):
        self._frame = bytearray()

        self._frame.append(self.MESSAGE_TYPE)

        length: int = 4
        self._frame.append(length)
        self._frame.append(address)
        self._frame.append(self._port)
        self._frame.append(payload_type)
        self._frame.append(self.calculate_checksum())


class WriteHarpMessage(HarpMessage):
    """
    A write Harp message sent to a Harp device.

    Attributes
    ----------
    payload : Union[int, list[int]]
        the payload sent in the write Harp message
    """

    MESSAGE_TYPE: int = MessageType.WRITE

    # Define payload type properties
    _PAYLOAD_CONFIG = {
        # payload_type: (byte_size, signed, is_float)
        PayloadType.U8: (1, False, False),
        PayloadType.S8: (1, True, False),
        PayloadType.U16: (2, False, False),
        PayloadType.S16: (2, True, False),
        PayloadType.U32: (4, False, False),
        PayloadType.S32: (4, True, False),
        PayloadType.U64: (8, False, False),
        PayloadType.S64: (8, True, False),
        PayloadType.Float: (4, False, True),
    }

    def __init__(
        self,
        payload_type: PayloadType,
        address: int,
        value: int | float | List[int] | List[float] = None,
    ):
        """
        Create a WriteHarpMessage to send to a device.

        Parameters
        ----------
        payload_type : PayloadType
            Type of payload (U8, S8, U16, etc.)
        address : int
            Register address to write to
        value : int, float, List[int], or List[float], optional
            Value(s) to write - can be a single value or list of values

        Note
        -----
        The message frame is constructed according to the HARP binary protocol.
        The length is calculated as BASE_LENGTH + payload size in bytes.
        """

        self._frame = bytearray()

        # Get configuration for this payload type
        byte_size, signed, is_float = self._PAYLOAD_CONFIG.get(
            payload_type, (1, False, False)
        )

        # Convert value to payload bytes
        payload = bytearray()
        values = value if isinstance(value, list) else [value]

        for val in values:
            if is_float:
                payload += struct.pack("<f", val)
            else:
                payload += val.to_bytes(byte_size, byteorder="little", signed=signed)

        # Build the frame
        self._frame.append(self.MESSAGE_TYPE)
        # Length is BASE_LENGTH + payload size
        self._frame.append(self.BASE_LENGTH + len(payload))
        self._frame.append(address)
        self._frame.append(self._port)
        self._frame.append(payload_type)
        self._frame += payload
        self._frame.append(self.calculate_checksum())
