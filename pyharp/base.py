from enum import IntEnum

# Bit masks for the PayloadType
_isUnsigned: int = 0x00
_isSigned: int = 0x80
_isFloat: int = 0x40
_hasTimestamp: int = 0x10


class MessageType(IntEnum):
    """
    An enumeration of the allowed message types of a Harp message. More information on the MessageType byte of a Harp message can be found [here](https://harp-tech.org/protocol/BinaryProtocol-8bit.html#messagetype-1-byte).

    Attributes
    ----------
    READ : int
        the value that corresponds to a Read Harp message (1)
    WRITE : int
        the value that corresponds to a Write Harp message (2)
    EVENT : int
        the value that corresponds to an Event Harp message (3). Messages of this type are only meant to be send by the device
    READ_ERROR : int
        the value that corresponds to a Read Error Harp message (9). Messages of this type are only meant to be send by the device
    WRITE_ERROR : int
        the value that corresponds to a Write Error Harp message (10). Messages of this type are only meant to be send by the device
    """

    READ: int = 1
    WRITE: int = 2
    EVENT: int = 3
    READ_ERROR: int = 9
    WRITE_ERROR: int = 10


class PayloadType(IntEnum):
    """
    An enumeration of the allowed payload types of a Harp message. More information on the PayloadType byte of a Harp message can be found [here](https://harp-tech.org/protocol/BinaryProtocol-8bit.html#payloadtype-1-byte).

    Attributes
    ----------
    U8 : PayloadType
        the value that corresponds to a message of type U8
    S8 : PayloadType
        the value that corresponds to a message of type S8
    U16 : PayloadType
        the value that corresponds to a message of type U16
    S16 : PayloadType
        the value that corresponds to a message of type S16
    U32 : PayloadType
        the value that corresponds to a message of type U32
    S32 : PayloadType
        the value that corresponds to a message of type S32
    U64 : PayloadType
        the value that corresponds to a message of type U64
    S64 : PayloadType
        the value that corresponds to a message of type S64
    Float : PayloadType
        the value that corresponds to a message of type Float
    TimestampedU8 : PayloadType
        the value that corresponds to a message of type TimestampedU8
    TimestampedS8 : PayloadType
        the value that corresponds to a message of type TimestampedS8
    TimestampedU16 : PayloadType
        the value that corresponds to a message of type TimestampedU16
    TimestampedS16 : PayloadType
        the value that corresponds to a message of type TimestampedS16
    TimestampedU32 : PayloadType
        the value that corresponds to a message of type TimestampedU32
    TimestampedS32 : PayloadType
        the value that corresponds to a message of type TimestampedS32
    TimestampedU64 : PayloadType
        the value that corresponds to a message of type TimestampedU64
    TimestampedS64 : PayloadType
        the value that corresponds to a message of type TimestampedS64
    TimestampedFloat : PayloadType
        the value that corresponds to a message of type TimestampedFloat
    """

    U8 = _isUnsigned | 1
    S8 = _isSigned | 1
    U16 = _isUnsigned | 2
    S16 = _isSigned | 2
    U32 = _isUnsigned | 4
    S32 = _isSigned | 4
    U64 = _isUnsigned | 8
    S64 = _isSigned | 8
    Float = _isFloat | 4
    TimestampedU8 = _hasTimestamp | U8
    TimestampedS8 = _hasTimestamp | S8
    TimestampedU16 = _hasTimestamp | U16
    TimestampedS16 = _hasTimestamp | S16
    TimestampedU32 = _hasTimestamp | U32
    TimestampedS32 = _hasTimestamp | S32
    TimestampedU64 = _hasTimestamp | U64
    TimestampedS64 = _hasTimestamp | S64
    TimestampedFloat = _hasTimestamp | Float


class CommonRegisters(IntEnum):
    """
    An enumeration with the registers that are common to every Harp device. More information on the common registers can be found [here](https://harp-tech.org/protocol/Device.html#table---list-of-available-common-registers).

    WHO_AM_I : int
        the number of the `WHO_AM_I` register
    HW_VERSION_H : int
        the number of the `HW_VERSION_H` register
    HW_VERSION_L : int
        the number of the `HW_VERSION_L` register
    ASSEMBLY_VERSION : int
        the number of the `ASSEMBLY_VERSION` register
    HARP_VERSION_H : int
        the number of the `HARP_VERSION_H` register
    HARP_VERSION_L : int
        the number of the `HARP_VERSION_L` register
    FIRMWARE_VERSION_H : int
        the number of the `FIRMWARE_VERSION_H` register
    FIRMWARE_VERSION_L : int
        the number of the `FIRMWARE_VERSION_L` register
    TIMESTAMP_SECOND : int
        the number of the `TIMESTAMP_SECOND` register
    TIMESTAMP_MICRO : int
        the number of the `TIMESTAMP_MICRO` register
    OPERATION_CTRL : int
        the number of the `OPERATION_CTRL` register
    RESET_DEV : int
        the number of the `RESET_DEV` register
    DEVICE_NAME : int
        the number of the `DEVICE_NAME` register
    SERIAL_NUMBER : int
        the number of the `SERIAL_NUMBER` register
    """

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


class DeviceMode(IntEnum):
    Standby = 0
    Active = 1
    Reserved = 2
    Speed = 3
