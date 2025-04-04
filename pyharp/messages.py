from __future__ import annotations  # for type hints (PEP 563)

import struct
from typing import List, Union

from pyharp.base import MessageType, PayloadType


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
        """
        Calculates the checksum of the Harp message.

        Returns
        -------
        int
            the value of the checksum
        """
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
    _frame: bytearray

    def __init__(self):
        self._frame = bytearray()

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


# A Response Message from a harp device.
class ReplyHarpMessage(HarpMessage):
    """
    A Response Message from a harp device.
    """

    def __init__(
        self,
        frame: bytearray,
    ):
        """

        :param frame: the serialized message frame.
        """

        self._frame = frame
        # retrieve all content from 11 (where payload starts) until the checksum (not inclusive)
        self._raw_payload = frame[11:-1]
        self._payload = self._parse_payload(
            self._raw_payload
        )  # payload formatted as list[payload type]

        # Assign timestamp after _payload since @properties all rely on self._payload.
        self._timestamp = (
            int.from_bytes(frame[5:9], byteorder="little", signed=False)
            + int.from_bytes(frame[9:11], byteorder="little", signed=False) * 32e-6
        )
        # Timestamp is junk if it's not present.
        if not (self.payload_type.value & PayloadType.Timestamp.value):
            self._timestamp = None

    def _parse_payload(self, raw_payload) -> list[int]:
        """return the payload as a list of ints after parsing it from the raw payload."""
        is_signed = True if (self.payload_type.value & 0x80) else False
        is_float = True if (self.payload_type.value & 0x40) else False
        bytes_per_word = self.payload_type.value & 0x07
        payload_len = len(raw_payload)  # payload length in bytes.

        word_chunks = [
            raw_payload[i : i + bytes_per_word]
            for i in range(0, payload_len, bytes_per_word)
        ]
        if not is_float:
            return [
                int.from_bytes(chunk, byteorder="little", signed=is_signed)
                for chunk in word_chunks
            ]
        else:  # handle float case.
            return [struct.unpack("<f", chunk)[0] for chunk in word_chunks]

    def __repr__(self):
        """Print debug representation of a reply message."""
        return self.__str__() + f"\r\nRaw Frame: {self.frame}"

    def __str__(self):
        """Print friendly representation of a reply message."""
        payload_str = ""
        format_str = ""
        if self.payload_type in [PayloadType.Float, PayloadType.TimestampedFloat]:
            format_str = ".6f"
        else:
            bytes_per_word = self.payload_type.value & 0x07
            format_str = f"0{bytes_per_word}b"

        payload_str = "".join(f"{item:{format_str}} " for item in self.payload)

        return (
            f"Type: {self.message_type.name}\r\n"
            + f"Length: {self.length}\r\n"
            + f"Address: {self.address}\r\n"
            + f"Port: {self.port}\r\n"
            + f"Timestamp: {self.timestamp}\r\n"
            + f"Payload Type: {self.payload_type.name}\r\n"
            + f"Payload Length: {len(self.payload)}\r\n"
            + f"Payload: {payload_str}\r\n"
            + f"Checksum: {self.checksum}"
        )

    @property
    def payload(self) -> Union[int, list[int]]:
        """return the payload formatted as the appropriate type."""
        return self._payload

    @property
    def timestamp(self) -> float:
        return self._timestamp

    def payload_as_int(self) -> int:
        return self.payload[0]

    def payload_as_string(self) -> str:
        return self._raw_payload.decode("utf-8")

    def payload_as_float(self) -> float:
        return self.payload[0]  # already parsed.


# A Read Request Message sent to a harp device.
class ReadHarpMessage(HarpMessage):
    MESSAGE_TYPE: int = MessageType.READ

    def __init__(self, payload_type: PayloadType, address: int):
        self._frame = bytearray()

        self._frame.append(self.MESSAGE_TYPE.value)

        length: int = 4
        self._frame.append(length)
        self._frame.append(address)
        self._frame.append(self.DEFAULT_PORT)
        self._frame.append(payload_type.value)
        self._frame.append(self.calculate_checksum())


class WriteHarpMessage(HarpMessage):
    BASE_LENGTH: int = 5
    BASE_LENGTH: int = 4
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

        Notes
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
        self._frame.append(self.MESSAGE_TYPE.value)
        # Length is BASE_LENGTH + payload size
        self._frame.append(self.BASE_LENGTH + len(payload))
        self._frame.append(address)
        self._frame.append(self.DEFAULT_PORT)
        self._frame.append(payload_type.value)
        self._frame += payload
        self._frame.append(self.calculate_checksum())

    @property
    def payload(self) -> Union[int, list[int]]:
        match self.payload_type:
            case PayloadType.U8:
                return self._frame[5]
            case PayloadType.S8:
                return int.from_bytes([self.frame[5]], byteorder="little", signed=True)
            case PayloadType.U16:
                return int.from_bytes(
                    self._frame[5:7], byteorder="little", signed=False
                )
            case PayloadType.S16:
                return int.from_bytes(self._frame[5:7], byteorder="little", signed=True)
            case PayloadType.Float:
                return struct.unpack("<f", self._frame[5:9])[0]
            case PayloadType.U32:
                return int.from_bytes(
                    self._frame[5:9], byteorder="little", signed=False
                )
            case PayloadType.S32:
                return int.from_bytes(self._frame[5:9], byteorder="little", signed=True)
            case PayloadType.U64:
                return int.from_bytes(
                    self._frame[5:13], byteorder="little", signed=False
                )
            case PayloadType.S64:
                return int.from_bytes(
                    self._frame[5:13], byteorder="little", signed=True
                )
            case _:
                return self._frame[5:]
