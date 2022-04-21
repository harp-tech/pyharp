from __future__ import annotations # for type hints (PEP 563)
from enum import Enum
# from abc import ABC, abstractmethod
from typing import Union, Tuple, Optional


class MessageType(Enum):
    READ: int = 1
    WRITE: int = 2
    EVENT: int = 3
    READ_ERROR: int = 9
    WRITE_ERROR: int = 10


class PayloadType(Enum):
    isUnsigned: int = 0x00
    isSigned: int = 0x80
    isFloat: int = 0x40
    hasTimestamp: int = 0x10

    U8 = isUnsigned | 1  # 1
    S8 = isSigned | 1  # 129
    U16 = isUnsigned | 2  # 2
    S16 = isSigned | 2  # 130
    U32 = isUnsigned | 4
    S32 = isSigned | 4
    U64 = isUnsigned | 8
    S64 = isSigned | 8
    Float = isFloat | 4
    Timestamp = hasTimestamp
    TimestampedU8 = hasTimestamp | U8
    TimestampedS8 = hasTimestamp | S8
    TimestampedU16 = hasTimestamp | U16
    TimestampedS16 = hasTimestamp | S16
    TimestampedU32 = hasTimestamp | U32
    TimestampedS32 = hasTimestamp | S32
    TimestampedU64 = hasTimestamp | U64
    TimestampedS64 = hasTimestamp | S64
    TimestampedFloat = hasTimestamp | Float


ALL_UNSIGNED = [PayloadType.U8,
                PayloadType.U16,
                PayloadType.U32,
                PayloadType.TimestampedU8,
                PayloadType.TimestampedU16]
ALL_SIGNED = [PayloadType.S8,
              PayloadType.S16,
              PayloadType.S32,
              PayloadType.TimestampedS8,
              PayloadType.TimestampedS16]


class CommonRegisters:
    WHO_AM_I = 0x00
    HW_VERSION_H = 0x01
    HW_VERSION_L = 0x02
    ASSEMBLY_VERSION = 0x03
    HARP_VERSION_H = 0x04
    HARP_VERSION_L = 0x05
    FIRMWARE_VERSION_H = 0x06
    FIRMWARE_VERSION_L = 0x07
    TIMESTAMP_SECOND = 0x08
    TIMESTAMP_MICRO = 0x09
    OPERATION_CTRL = 0x0A
    RESET_DEV = 0x0B
    DEVICE_NAME = 0x0C


class HarpMessage:
    """
    https://github.com/harp-tech/protocol/blob/master/Binary%20Protocol%201.0%201.1%2020180223.pdf
    """

    DEFAULT_PORT: int = 255
    _frame: bytearray

    def __init__(self):
        self._frame = bytearray()

    def calculate_checksum(self) -> int:
        checksum: int = 0
        for i in self.frame:
            checksum += i
        return checksum & 255

    @property
    def frame(self) -> bytearray:
        return self._frame

    @property
    def message_type(self) -> MessageType:
        return MessageType(self._frame[0])

    @property
    def length(self) -> int:
        return self._frame[1]

    @property
    def address(self) -> int:
        return self._frame[2]

    @property
    def port(self) -> int:
        return self._frame[3]

    @property
    def payload_type(self) -> int:
        return PayloadType(self._frame[4])

    @property
    def checksum(self) -> int:
        return self._frame[-1]

    @staticmethod
    def ReadU8(address: int) -> ReadU8HarpMessage:
        return ReadU8HarpMessage(address)

    @staticmethod
    def ReadS8(address: int) -> ReadS8HarpMessage:
        return ReadS8HarpMessage(address)

    @staticmethod
    def ReadS16(address: int) -> ReadS16HarpMessage:
        return ReadS16HarpMessage(address)

    @staticmethod
    def ReadU16(address: int) -> ReadU16HarpMessage:
        return ReadU16HarpMessage(address)

    @staticmethod
    def WriteU8(address: int, value: int) -> WriteU8HarpMessage:
        return WriteU8HarpMessage(address, value)

    @staticmethod
    def WriteS8(address: int, value: int) -> WriteS8HarpMessage:
        return WriteS8HarpMessage(address, value)

    @staticmethod
    def WriteS16(address: int, value: int) -> WriteS16HarpMessage:
        return WriteS16HarpMessage(address, value)

    @staticmethod
    def WriteU16(address: int, value: int) -> WriteU16HarpMessage:
        return WriteU16HarpMessage(address, value)

    @staticmethod
    def parse(frame: bytearray) -> ReplyHarpMessage:
        return ReplyHarpMessage(frame)


# A Response Message from a harp device.
class ReplyHarpMessage(HarpMessage):


    def __init__(
        self, frame: bytearray,
    ):
        """

        :param frame: the serialized message frame.
        """

        self._frame = frame
        # retrieve all content from 11 (where payload starts) until the checksum (not inclusive)
        self._payload = frame[11:-1]

        # Assign timestamp after _payload since @properties all rely on self._payload.
        self._timestamp = int.from_bytes(frame[5:9], byteorder="little", signed=False) + \
                          int.from_bytes(frame[9:11], byteorder="little", signed=False)*32e-6
        # Timestamp is junk if it's not present.
        if self.payload_type.value & PayloadType.hasTimestamp.value:
            self._timestamp = None


    def __repr__(self):
        """Print debug representation of a reply message."""
        print(self.__str__())
        print(f"Raw Frame: {self.frame}")


    def __str__(self):
        """Print friendly representation of a reply message."""
        payload_str = ""
        format_str = ""
        if self.payload_type.value & 0x01:
            format_str = '08b'
        elif self.payload_type.value & 0x02:
            format_str = '016b'
        elif self.payload_type.value & 0x04:
            if self.message_type.value & PayloadType.isFloat.value:
                format_str = '.6f'
            else:
                format_str = '032b'
        elif self.payload_type.value & 0x08:
            format_str = '064b'

        for item in self.payload:
            payload_str += f"{item:{format_str}} "

        return f"Type: {self.message_type.name}\r\n" + \
               f"Length: {self.length}\r\n" + \
               f"Address: {self.address}\r\n" + \
               f"Port: {self.port}\r\n" + \
               f"Timestamp: {self.timestamp}\r\n" + \
               f"Payload Type: {self.payload_type.name}\r\n" + \
               f"Payload Length: {len(self.payload)}\r\n" + \
               f"Payload: {payload_str}\r\n" + \
               f"Checksum: {self.checksum}"

    @property
    def payload(self) -> bytes:
        return self._payload

    @property
    def timestamp(self) -> float:
        return self._timestamp

    def payload_as_int(self) -> int:
        value: int = 0
        if self.payload_type in ALL_UNSIGNED:
            value = int.from_bytes(self.payload, byteorder="little", signed=False)
        elif self.payload_type in ALL_SIGNED:
            value = int.from_bytes(self.payload, byteorder="little", signed=True)
        return value

    def payload_as_int_array(self) -> list:
        # Number of bytes per chunk. Get this from the bit field structure.
        datatype_bytes = 0x0F & self.payload_type.value
        # TODO: is len(self.payload) == self.length?
        signed = True if self.payload_type in ALL_UNSIGNED else False
        # Break the payload into chunks of datatype size in bytes
        byte_chunks = [self.payload[i: i+datatype_bytes] for i in range(0, len(self.payload), datatype_bytes)]
        return [int.from_bytes(chunk, byteorder="little", signed=signed) for chunk in byte_chunks]

    def payload_as_string(self) -> str:
        return self.payload.decode("utf-8")


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


class ReadU8HarpMessage(ReadHarpMessage):
    def __init__(self, address: int):
        super().__init__(PayloadType.U8, address)


class ReadS8HarpMessage(ReadHarpMessage):
    def __init__(self, address: int):
        super().__init__(PayloadType.S8, address)


class ReadU16HarpMessage(ReadHarpMessage):
    def __init__(self, address: int):
        super().__init__(PayloadType.U16, address)


class ReadS16HarpMessage(ReadHarpMessage):
    def __init__(self, address: int):
        super().__init__(PayloadType.S16, address)


class WriteHarpMessage(HarpMessage):
    BASE_LENGTH: int = 5
    MESSAGE_TYPE: int = MessageType.WRITE

    def __init__(
        self, payload_type: PayloadType, payload: bytes, address: int, offset: int = 0
    ):
        """

        :param payload_type:
        :param payload:
        :param address:
        :param offset: how many bytes more besides the length corresponding to U8 (for example, for U16 it would be offset=1)
        """
        self._frame = bytearray()

        self._frame.append(self.MESSAGE_TYPE.value)

        self._frame.append(self.BASE_LENGTH + offset)

        self._frame.append(address)
        self._frame.append(HarpMessage.DEFAULT_PORT)
        self._frame.append(payload_type.value)

        for i in payload:
            self._frame.append(i)

        self._frame.append(self.calculate_checksum())


class WriteU8HarpMessage(WriteHarpMessage):
    def __init__(self, address: int, value: int):
        super().__init__(PayloadType.U8, value.to_bytes(1, byteorder="little"), address)

    @property
    def payload(self) -> int:
        return self.frame[5]


class WriteS8HarpMessage(WriteHarpMessage):
    def __init__(self, address: int, value: int):
        super().__init__(
            PayloadType.S8, value.to_bytes(1, byteorder="little", signed=True), address
        )

    @property
    def payload(self) -> int:
        return int.from_bytes([self.frame[5]], byteorder="little", signed=True)


class WriteU16HarpMessage(WriteHarpMessage):
    def __init__(self, address: int, value: int):
        super().__init__(
            PayloadType.U16, value.to_bytes(2, byteorder="little", signed=False), address, offset=1
        )

    @property
    def payload(self) -> int:
        return int.from_bytes(self._frame[5:7], byteorder="little", signed=False)


class WriteS16HarpMessage(WriteHarpMessage):
    def __init__(self, address: int, value: int):
        super().__init__(
            PayloadType.S16,
            value.to_bytes(2, byteorder="little", signed=True),
            address,
            offset=1,
        )

    @property
    def payload(self) -> int:
        return int.from_bytes(self._frame[5:7], byteorder="little", signed=True)
