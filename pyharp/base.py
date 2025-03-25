from enum import Enum


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
