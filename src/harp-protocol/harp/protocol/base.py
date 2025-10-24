from datetime import datetime
from enum import IntEnum, IntFlag

# The reference epoch for UTC harp time
REFERENCE_EPOCH = datetime(1904, 1, 1)


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

    READ = 0x01
    WRITE = 0x02
    EVENT = 0x03
    ERROR = 0x08
    READ_ERROR = READ | ERROR
    WRITE_ERROR = WRITE | ERROR

    def is_error(self):
        return bool(self & MessageType.ERROR)


class _PayloadTypeFlags(IntEnum):
    """
    Internal flags used to define the PayloadType enumeration.

    Attributes
    ----------
    HAS_TIMESTAMP : int
        Flag indicating that the message has a timestamp
    IS_FLOAT : int
        Flag indicating that the message payload is a float
    IS_SIGNED : int
        Flag indicating that the message payload is signed
    TYPE_SIZE : int
        Mask to get the size of the message payload in bytes
    """

    HAS_TIMESTAMP = 0x10
    IS_FLOAT = 0x40
    IS_SIGNED = 0x80
    TYPE_SIZE = 0x0F


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
    FLOAT : int
        The value that corresponds to a message of type Float
    TIMESTAMP : int
        The value that corresponds to a message of type Timestamp. This is not a valid PayloadType, but it is used to indicate that the message has a timestamp.
    TIMESTAMPED_U8 : int
        The value that corresponds to a message of type TimestampedU8
    TIMESTAMPED_S8 : int
        The value that corresponds to a message of type TimestampedS8
    TIMESTAMPED_U16 : int
        The value that corresponds to a message of type TimestampedU16
    TIMESTAMPED_S16 : int
        The value that corresponds to a message of type TimestampedS16
    TIMESTAMPED_U32 : int
        The value that corresponds to a message of type TimestampedU32
    TIMESTAMPED_S32 : int
        The value that corresponds to a message of type TimestampedS32
    TIMESTAMPED_U64 : int
        The value that corresponds to a message of type TimestampedU64
    TIMESTAMPED_S64 : int
        The value that corresponds to a message of type TimestampedS64
    TIMESTAMPED_FLOAT : int
        The value that corresponds to a message of type TimestampedFloat
    """

    U8 = 0x01
    S8 = _PayloadTypeFlags.IS_SIGNED | 0x01
    U16 = 0x02
    S16 = _PayloadTypeFlags.IS_SIGNED | 0x02
    U32 = 0x04
    S32 = _PayloadTypeFlags.IS_SIGNED | 0x04
    U64 = 0x08
    S64 = _PayloadTypeFlags.IS_SIGNED | 0x08
    FLOAT = _PayloadTypeFlags.IS_FLOAT | 0x04
    TIMESTAMPED_U8 = _PayloadTypeFlags.HAS_TIMESTAMP | U8
    TIMESTAMPED_S8 = _PayloadTypeFlags.HAS_TIMESTAMP | S8
    TIMESTAMPED_U16 = _PayloadTypeFlags.HAS_TIMESTAMP | U16
    TIMESTAMPED_S16 = _PayloadTypeFlags.HAS_TIMESTAMP | S16
    TIMESTAMPED_U32 = _PayloadTypeFlags.HAS_TIMESTAMP | U32
    TIMESTAMPED_S32 = _PayloadTypeFlags.HAS_TIMESTAMP | S32
    TIMESTAMPED_U64 = _PayloadTypeFlags.HAS_TIMESTAMP | U64
    TIMESTAMPED_S64 = _PayloadTypeFlags.HAS_TIMESTAMP | S64
    TIMESTAMPED_FLOAT = _PayloadTypeFlags.HAS_TIMESTAMP | FLOAT

    def has_timestamp(self):
        """
        bool
            Returns True if this PayloadType has a timestamp, False otherwise.
        """
        return bool(self & _PayloadTypeFlags.HAS_TIMESTAMP)

    def is_float(self):
        """
        bool
            Returns True if this PayloadType is a float, False otherwise.
        """
        return bool(self & _PayloadTypeFlags.IS_FLOAT)

    def is_signed(self):
        """
        bool
            Returns True if this PayloadType is signed, False otherwise.
        """
        return bool(self & _PayloadTypeFlags.IS_SIGNED)

    def type_size(self):
        return self & _PayloadTypeFlags.TYPE_SIZE


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
    CORE_VERSION_H : int
        The number of the `CORE_VERSION_H` register
    CORE_VERSION_L : int
        The number of the `CORE_VERSION_L` register
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
    CORE_VERSION_H = 0x04
    CORE_VERSION_L = 0x05
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

    STANDBY = 0x00
    ACTIVE = 0x01
    RESERVED = 0x02
    SPEED = 0x03


class OperationCtrl(IntFlag):
    """
    An enumeration with the operation control bits of a Harp device. More information on the operation control bits can be found [here](https://harp-tech.org/protocol/Device.html#r_operation_ctrl-u16--operation-mode-configuration).

    Attributes
    ----------
    OP_MODE : int
        Operation mode of the device.
            0: Standby Mode (all Events off, mandatory)
            1: Active Mode (Events detection enabled, mandatory)
            2: Reserved
            3: Speed Mode (device enters Speed Mode, optional; only responds to Speed Mode commands)
    DUMP : int
        When set to 1, the device adds the content of all registers to the streaming buffer as Read messages. Always read as 0
    MUTE_RPL : int
        If set to 1, replies to all commands are muted (not sent by the device)
    VISUALEN : int
        If set to 1, visual indications (e.g., LEDs) operate. If 0, all visual indications are turned off
    OPLEDEN : int
        If set to 1, the LED indicates the selected Operation Mode (see LED feedback table in documentation)
    ALIVE_EN : int
        If set to 1, the device sends an Event Message with the R_TIMESTAMP_SECONDS content each second (heartbeat)
    """

    OP_MODE = 0x03
    DUMP = 0x08
    MUTE_RPL = 0x10
    VISUALEN = 0x20
    OPLEDEN = 0x40
    ALIVE_EN = 0x80


class ResetMode(IntEnum):
    """
    An enumeration with the reset modes and actions for the R_RESET_DEV register of a Harp device.
    More information on the reset modes can be found [here](https://harp-tech.org/protocol/Device.html#r_reset_dev-u8--reset-device-and-save-non-volatile-registers).

    Attributes
    ----------
    RST_DEF : int
        If set, resets the device and restores all registers (Common and Application) to default values.
        EEPROM is erased and defaults become the permanent boot option
    RST_EE : int
        If set, resets the device and restores all registers (Common and Application) from non-volatile memory (EEPROM).
        EEPROM values remain the permanent boot option
    SAVE : int
        If set, saves all non-volatile registers (Common and Application) to EEPROM and reboots.
        EEPROM becomes the permanent boot option
    NAME_TO_DEFAULT : int
        If set, reboots the device with the default name
    BOOT_DEF : int
        If set, indicates the device booted with default register values
    BOOT_EE : int
        If set, indicates the device booted with register values saved on the EEPROM
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
        If set to 1, the device will repeat the Harp Synchronization Clock to the Clock Output connector, if available.
        Acts as a daisy-chain by repeating the Clock Input to the Clock Output. Setting this bit also unlocks the Harp Synchronization Clock
    CLK_GEN : int
        If set to 1, the device will generate Harp Synchronization Clock to the Clock Output connector, if available.
        The Clock Input will be ignored. Read as 1 if the device is generating the Harp Synchronization Clock
    REP_ABLE : int
        If set, indicates if the device is able (1) to repeat the Harp Synchronization Clock timestamp
    GEN_ABLE : int
        If set, indicates if the device is able (1) to generate the Harp Synchronization Clock timestamp
    CLK_UNLOCK : int
        If set to 1, the device will unlock the timestamp register counter (R_TIMESTAMP_SECOND) and accept new timestamp values.
        Read as 1 if the timestamp register is unlocked
    CLK_LOCK : int
        If set to 1, the device will lock the current timestamp register counter (R_TIMESTAMP_SECOND) and reject new timestamp values.
        Read as 1 if the timestamp register is locked
    """

    CLK_REP = 0x01
    CLK_GEN = 0x02
    REP_ABLE = 0x08
    GEN_ABLE = 0x10
    CLK_UNLOCK = 0x40
    CLK_LOCK = 0x80
