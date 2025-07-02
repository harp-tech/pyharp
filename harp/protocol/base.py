from enum import IntEnum, IntFlag

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
        The value that corresponds to a Read Harp message (1)
    WRITE : int
        The value that corresponds to a Write Harp message (2)
    EVENT : int
        The value that corresponds to an Event Harp message (3). Messages of this type are only meant to be send by the device
    READ_ERROR : int
        The value that corresponds to a Read Error Harp message (9). Messages of this type are only meant to be send by the device
    WRITE_ERROR : int
        The value that corresponds to a Write Error Harp message (10). Messages of this type are only meant to be send by the device
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
    U8 : int
        The value that corresponds to a message of type U8
    S8 : int
        The value that corresponds to a message of type S8
    U16 : int
        The value that corresponds to a message of type U16
    S16 : int
        The value that corresponds to a message of type S16
    U32 : int
        The value that corresponds to a message of type U32
    S32 : int
        The value that corresponds to a message of type S32
    U64 : int
        The value that corresponds to a message of type U64
    S64 : int
        The value that corresponds to a message of type S64
    Float : int
        The value that corresponds to a message of type Float
    Timestamp: int
        The value that corresponds to a message of type Timestamp. This is not a valid PayloadType, but it is used to indicate that the message has a timestamp.
    TimestampedU8 : int
        The value that corresponds to a message of type TimestampedU8
    TimestampedS8 : int
        The value that corresponds to a message of type TimestampedS8
    TimestampedU16 : int
        The value that corresponds to a message of type TimestampedU16
    TimestampedS16 : int
        The value that corresponds to a message of type TimestampedS16
    TimestampedU32 : int
        The value that corresponds to a message of type TimestampedU32
    TimestampedS32 : int
        The value that corresponds to a message of type TimestampedS32
    TimestampedU64 : int
        The value that corresponds to a message of type TimestampedU64
    TimestampedS64 : int
        The value that corresponds to a message of type TimestampedS64
    TimestampedFloat : int
        The value that corresponds to a message of type TimestampedFloat
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


class CommonRegisters(IntEnum):
    """
    An enumeration with the registers that are common to every Harp device. More information on the common registers can be found [here](https://harp-tech.org/protocol/Device.html#table---list-of-available-common-registers).

    Attributes
    ----------
    WHO_AM_I : int
        The number of the `WHO_AM_I` register
    HW_VERSION_H : int
        The number of the `HW_VERSION_H` register
    HW_VERSION_L : int
        The number of the `HW_VERSION_L` register
    ASSEMBLY_VERSION : int
        The number of the `ASSEMBLY_VERSION` register
    HARP_VERSION_H : int
        The number of the `HARP_VERSION_H` register
    HARP_VERSION_L : int
        The number of the `HARP_VERSION_L` register
    FIRMWARE_VERSION_H : int
        The number of the `FIRMWARE_VERSION_H` register
    FIRMWARE_VERSION_L : int
        The number of the `FIRMWARE_VERSION_L` register
    TIMESTAMP_SECOND : int
        The number of the `TIMESTAMP_SECOND` register
    TIMESTAMP_MICRO : int
        The number of the `TIMESTAMP_MICRO` register
    OPERATION_CTRL : int
        The number of the `OPERATION_CTRL` register
    RESET_DEV : int
        The number of the `RESET_DEV` register
    DEVICE_NAME : int
        The number of the `DEVICE_NAME` register
    SERIAL_NUMBER : int
        The number of the `SERIAL_NUMBER` register
    CLOCK_CONFIG : int
        The number of the `CLOCK_CONFIG` register
    TIMESTAMP_OFFSET : int
        The number of the `TIMESTAMP_OFFSET` register
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
    CLOCK_CONFIG = 0x0E
    TIMESTAMP_OFFSET = 0x0F


class OperationMode(IntEnum):
    """
    An enumeration with the operation modes of a Harp device. More information on the operation modes can be found [here](https://harp-tech.org/protocol/Device.html#r_operation_ctrl-u16--operation-mode-configuration).

    Attributes
    ----------
    STANDBY : int
        The value that corresponds to the Standby operation mode (0). The device has all the Events turned off
    ACTIVE : int
        The value that corresponds to the Active operation mode (1). The device turns ON the Events detection. Only the enabled Events will be operating
    RESERVED : int
        The value that corresponds to the Reserved operation mode (2)
    SPEED : int
        The value that corresponds to the Speed operation mode (3). The device enters Speed Mode
    """

    STANDBY = 0
    ACTIVE = 1
    RESERVED = 2
    SPEED = 3


class OperationCtrl(IntFlag):
    """
    An enumeration with the operation control bits of a Harp device. More information on the operation control bits can be found [here](https://harp-tech.org/protocol/Device.html#r_operation_ctrl-u16--operation-mode-configuration).

    Attributes
    ----------
    OP_MODE : int
        Bits 1:0 (0x03): Operation mode of the device.
            0: Standby Mode (all Events off, mandatory)
            1: Active Mode (Events detection enabled, mandatory)
            2: Reserved
            3: Speed Mode (device enters Speed Mode, optional; only responds to Speed Mode commands)
    DUMP : int
        Bit 3 (0x08): When set to 1, the device adds the content of all registers to the streaming buffer as Read messages. Always read as 0
    MUTE_RPL : int
        Bit 4 (0x10): If set to 1, replies to all commands are muted (not sent by the device)
    VISUALEN : int
        Bit 5 (0x20): If set to 1, visual indications (e.g., LEDs) operate. If 0, all visual indications are turned off
    OPLEDEN : int
        Bit 6 (0x40): If set to 1, the LED indicates the selected Operation Mode (see LED feedback table in documentation)
    ALIVE_EN : int
        Bit 7 (0x80): If set to 1, the device sends an Event Message with the R_TIMESTAMP_SECONDS content each second (heartbeat)
    """

    OP_MODE = 3 << 0
    DUMP = 1 << 3
    MUTE_RPL = 1 << 4
    VISUALEN = 1 << 5
    OPLEDEN = 1 << 6
    ALIVE_EN = 1 << 7


class ResetMode(IntEnum):
    """
    An enumeration with the reset modes and actions for the R_RESET_DEV register of a Harp device.
    More information on the reset modes can be found [here](https://harp-tech.org/protocol/Device.html#r_reset_dev-u8--reset-device-and-save-non-volatile-registers).

    Attributes
    ----------
    RST_DEF : int
        Bit 0 (0x01): If set, resets the device and restores all registers (Common and Application) to default values.
        EEPROM is erased and defaults become the permanent boot option
    RST_EE : int
        Bit 1 (0x02): If set, resets the device and restores all registers (Common and Application) from non-volatile memory (EEPROM).
        EEPROM values remain the permanent boot option
    SAVE : int
        Bit 3 (0x08): If set, saves all non-volatile registers (Common and Application) to EEPROM and reboots.
        EEPROM becomes the permanent boot option
    NAME_TO_DEFAULT : int
        Bit 4 (0x10): If set, reboots the device with the default name
    BOOT_DEF : int
        Bit 6 (0x40, read-only): Indicates the device booted with default register values
    BOOT_EE : int
        Bit 7 (0x80, read-only): Indicates the device booted with register values saved on the EEPROM
    """

    RST_DEF = 0x01
    RST_EE = 0x02
    SAVE = 0x08
    NAME_TO_DEFAULT = 0x10
    BOOT_DEF = 0x40
    BOOT_EE = 0x80


class ClockConfig(IntFlag):
    """
    An enumeration with the clock configuration bits for the R_CLOCK_CONFIG register of a Harp device.
    More information can be found [here](https://harp-tech.org/protocol/Device.html#r_clock_config-u8--synchronization-clock-configuration).

    Attributes
    ----------
    CLK_REP : int
        Bit 0 (0x01): If set to 1, the device will repeat the Harp Synchronization Clock to the Clock Output connector, if available.
        Acts as a daisy-chain by repeating the Clock Input to the Clock Output. Setting this bit also unlocks the Harp Synchronization Clock
    CLK_GEN : int
        Bit 1 (0x02): If set to 1, the device will generate Harp Synchronization Clock to the Clock Output connector, if available.
        The Clock Input will be ignored. Read as 1 if the device is generating the Harp Synchronization Clock
    REP_ABLE : int
        Bit 3 (0x08, read-only): Indicates if the device is able (1) to repeat the Harp Synchronization Clock timestamp
    GEN_ABLE : int
        Bit 4 (0x10, read-only): Indicates if the device is able (1) to generate the Harp Synchronization Clock timestamp
    CLK_UNLOCK : int
        Bit 6 (0x40): If set to 1, the device will unlock the timestamp register counter (R_TIMESTAMP_SECOND) and accept new timestamp values.
        Read as 1 if the timestamp register is unlocked
    CLK_LOCK : int
        Bit 7 (0x80): If set to 1, the device will lock the current timestamp register counter (R_TIMESTAMP_SECOND) and reject new timestamp values.
        Read as 1 if the timestamp register is locked
    """

    CLK_REP = 0x01
    CLK_GEN = 0x02
    REP_ABLE = 0x08
    GEN_ABLE = 0x10
    CLK_UNLOCK = 0x40
    CLK_LOCK = 0x80
