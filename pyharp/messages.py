# from abc import ABC, abstractmethod
from typing import Union, Tuple, Optional


class MessageType:
    READ: int = 1
    WRITE: int = 2
    EVENT: int = 3
    READ_ERROR: int = 9
    WRITE_ERROR: int = 10


class PayloadType:
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

    ALL_UNSIGNED = [U8, U16, U32, TimestampedU8, TimestampedU16]
    ALL_SIGNED = [S8, S16, S32, TimestampedS8, TimestampedS16]


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


T = Union[int, bytearray]


class HarpMessage:
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
    def message_type(self) -> int:
        return self._frame[0]

    @staticmethod
    def ReadU8(address: int) -> "ReadU8HarpMessage":
        return ReadU8HarpMessage(address)

    @staticmethod
    def ReadS8(address: int) -> "ReadS8HarpMessage":
        return ReadS8HarpMessage(address)

    @staticmethod
    def ReadS16(address: int) -> "ReadS16HarpMessage":
        return ReadS16HarpMessage(address)

    @staticmethod
    def ReadU16(address: int) -> "ReadU16HarpMessage":
        return ReadU16HarpMessage(address)

    @staticmethod
    def WriteU8(address: int, value: int) -> "WriteU8HarpMessage":
        return WriteU8HarpMessage(address, value)

    @staticmethod
    def WriteS8(address: int, value: int) -> "WriteS8HarpMessage":
        return WriteS8HarpMessage(address, value)

    @staticmethod
    def WriteS16(address: int, value: int) -> "WriteS16HarpMessage":
        return WriteS16HarpMessage(address, value)

    @staticmethod
    def WriteU16(address: int, value: int) -> "WriteU16HarpMessage":
        return WriteU16HarpMessage(address, value)

    @staticmethod
    def parse(frame: bytearray) -> "ReplyHarpMessage":
        return ReplyHarpMessage(frame)


class ReplyHarpMessage(HarpMessage):
    PAYLOAD_START_ADDRESS: int
    PAYLOAD_LAST_ADDRESS: int
    _message_type: int
    _length: int
    _address: int
    _payload_type: int
    _payload: bytes
    _checksum: int

    def __init__(
        self, frame: bytearray,
    ):
        """

        :param payload_type:
        :param payload:
        :param address:
        :param offset: how many bytes more besides the length corresponding to U8 (for example, for U16 it would be offset=1)
        """

        self._frame = frame

        self._message_type = frame[0]
        self._length = frame[1]
        self._address = frame[2]
        self._port = frame[3]
        self._payload_type = frame[4]
        # TOOO: add timestamp here
        self._payload = frame[
            11:-1
        ]  # retrieve all content from 11 (where payload starts) until the checksum (not inclusive)
        self._checksum = frame[-1]  # last index is the checksum

        # print(f"Type: {self.message_type}")
        # print(f"Length: {self.length}")
        # print(f"Address: {self.address}")
        # print(f"Port: {self.port}")
        # print(f"Payload Type: {self.payload_type}")
        # print(f"Payload: {self.payload}")
        # print(f"Checksum: {self.checksum}")
        # print(f"Frame: {self.frame}")

    @property
    def frame(self) -> bytearray:
        return self._frame

    @property
    def message_type(self) -> int:
        return self._message_type

    @property
    def length(self) -> int:
        return self._length

    @property
    def address(self) -> int:
        return self._address

    @property
    def port(self) -> int:
        return self._port

    @property
    def payload_type(self) -> int:
        return self._payload_type

    @property
    def payload(self) -> bytes:
        return self._payload

    def payload_as_int(self) -> int:
        value: int = 0
        if self.payload_type in PayloadType.ALL_UNSIGNED:
            value = int.from_bytes(self.payload, byteorder="little", signed=False)
        elif self.payload_type in PayloadType.ALL_SIGNED:
            value = int.from_bytes(self.payload, byteorder="little", signed=True)
        return value

    def payload_as_int_array(self):
        pass  # TODO: implement this

    def payload_as_string(self) -> str:
        return self.payload.decode("utf-8")

    @property
    def checksum(self) -> int:
        return self._checksum


class ReadHarpMessage(HarpMessage):
    MESSAGE_TYPE: int = MessageType.READ
    _length: int
    _address: int
    _payload_type: int
    _checksum: int

    def __init__(self, payload_type: int, address: int):
        self._frame = bytearray()

        self._frame.append(self.MESSAGE_TYPE)

        length: int = 4
        self._frame.append(length)

        self._frame.append(address)
        self._frame.append(self.DEFAULT_PORT)
        self._frame.append(payload_type)
        self._frame.append(self.calculate_checksum())

    # def calculate_checksum(self) -> int:
    #     return (
    #         self.message_type
    #         + self.length
    #         + self.address
    #         + self.port
    #         + self.payload_type
    #     ) & 255

    @property
    def message_type(self) -> int:
        return self._frame[0]

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
        return self._frame[4]

    @property
    def checksum(self) -> int:
        return self._frame[5]


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
    _length: int
    _address: int
    _payload_type: int
    _payload: int
    _checksum: int

    def __init__(
        self, payload_type: int, payload: bytes, address: int, offset: int = 0
    ):
        """

        :param payload_type:
        :param payload:
        :param address:
        :param offset: how many bytes more besides the length corresponding to U8 (for example, for U16 it would be offset=1)
        """
        self._frame = bytearray()

        self._frame.append(self.MESSAGE_TYPE)

        self._frame.append(self.BASE_LENGTH + offset)

        self._frame.append(address)
        self._frame.append(HarpMessage.DEFAULT_PORT)
        self._frame.append(payload_type)

        for i in payload:
            self._frame.append(i)

        self._frame.append(self.calculate_checksum())

    # def calculate_checksum(self) -> int:
    #     return (
    #         self.message_type
    #         + self.length
    #         + self.address
    #         + self.port
    #         + self.payload_type
    #         + self.payload
    #     ) & 255

    @property
    def message_type(self) -> int:
        return self._frame[0]

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
        return self._frame[4]

    @property
    def checksum(self) -> int:
        return self._frame[-1]


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
