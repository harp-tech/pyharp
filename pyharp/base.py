from enum import Enum

# TODO: Find a way to really hide this from the user
_isUnsigned: int = 0x00
_isSigned: int = 0x80
_isFloat: int = 0x40
_hasTimestamp: int = 0x10

class MessageType(Enum):
    READ: int = 1
    WRITE: int = 2
    EVENT: int = 3
    READ_ERROR: int = 9
    WRITE_ERROR: int = 10


class PayloadType(Enum):
    U8 = _isUnsigned | 1  # 1
    S8 = _isSigned | 1  # 129
    U16 = _isUnsigned | 2  # 2
    S16 = _isSigned | 2  # 130
    U32 = _isUnsigned | 4
    S32 = _isSigned | 4
    U64 = _isUnsigned | 8
    S64 = _isSigned | 8
    Float = _isFloat | 4
    Timestamp = _hasTimestamp
    TimestampedU8 = _hasTimestamp | U8
    TimestampedS8 = _hasTimestamp | S8
    TimestampedU16 = _hasTimestamp | U16
    TimestampedS16 = _hasTimestamp | S16
    TimestampedU32 = _hasTimestamp | U32
    TimestampedS32 = _hasTimestamp | S32
    TimestampedU64 = _hasTimestamp | U64
    TimestampedS64 = _hasTimestamp | S64
    TimestampedFloat = _hasTimestamp | Float


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
    SERIAL_NUMBER = 0x0D
