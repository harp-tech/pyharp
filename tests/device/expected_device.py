# This file was automatically generated and should not be edited directly.
# To make changes, edit the device metadata and regenerate the interface.

import enum
from typing import ClassVar

import numpy as np
from harp.device import CoreRegistersNamespace, Device
from harp.protocol import (
    AnonymousPayload,
    BitMask,
    BoolConverter,
    Field,
    GroupMask,
    HarpVersion,
    HarpVersionConverter,
    IdentityConverter,
    PayloadType,
    RegisterBase,
    RegisterS32,
    RegisterU8,
    RegisterU16,
    StringConverter,
    StructPayload,
)
from numpy.typing import NDArray

from .converters import (
    DataConverter,
)


class PortDigitalIOS(enum.IntFlag):
    DIO0 = 0x1
    DIO1 = 0x2
    DIO2 = 0x4
    DIO3 = 0x8
    DI_PORT0 = 0x100
    TEST_DI_PORT1 = 0x200
    SUPPLY_PORT0 = 0x400
    PORT_DIO1 = 0x800


class PwmPort(enum.IntEnum):
    PWM0 = 1
    PWM1 = 2
    PWM2 = 4
    PWM3 = 10


class EncoderModeMask(enum.IntEnum):
    """Specifies the type of encoder mode."""

    POSITION = 0
    DISPLACEMENT = 1


class AnalogDataPayload(StructPayload[np.float32], length=6):
    """Represents the payload of the AnalogData register."""

    analog0: np.float32 = Field(IdentityConverter(np.float32))
    analog1: np.float32 = Field(IdentityConverter(np.float32), offset=1)
    analog2: np.float32 = Field(IdentityConverter(np.float32), offset=2)
    accelerometer: NDArray[np.float32] = Field(
        IdentityConverter(np.dtype((np.float32, (3,)))), offset=3
    )


class ComplexConfigurationPayload(StructPayload[np.uint8], length=17):
    """Represents the payload of the ComplexConfiguration register."""

    pwm_port: PwmPort = GroupMask(enum=PwmPort, mask=0xFF)
    duty_cycle: np.float32 = Field(IdentityConverter(np.float32), offset=4)
    frequency: np.float32 = Field(IdentityConverter(np.float32), offset=8)
    events_enabled: bool = Field(BoolConverter(), offset=12)
    delta: np.uint32 = Field(IdentityConverter(np.uint32), offset=13)


class VersionPayload(StructPayload[np.uint8], length=32):
    """Represents the payload of the Version register."""

    protocol_version: HarpVersion = Field(HarpVersionConverter(np.uint8))
    firmware_version: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=3)
    hardware_version: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=6)
    core_id: str = Field(StringConverter(3), offset=9)
    interface_hash: NDArray[np.uint8] = Field(
        IdentityConverter(np.dtype((np.uint8, (20,)))), offset=12
    )


class CustomPayloadPayload(AnonymousPayload[np.uint32]):
    """Represents the payload of the CustomPayload register."""

    __value__: HarpVersion = Field(HarpVersionConverter(np.uint32))


class CustomRawPayloadPayload(AnonymousPayload[np.uint32]):
    """Represents the payload of the CustomRawPayload register."""

    __value__: HarpVersion = Field(HarpVersionConverter(np.uint32))


class CustomMemberConverterPayload(StructPayload[np.uint8], length=3):
    """Represents the payload of the CustomMemberConverter register."""

    header: np.uint8 = Field(IdentityConverter(np.uint8))
    data: np.int32 = Field(DataConverter(), offset=1)


class BitmaskSplitterPayload(StructPayload[np.uint8]):
    """Represents the payload of the BitmaskSplitter register."""

    low: np.int32 = Field(IdentityConverter(np.int32), mask=0xF)
    high: np.int32 = Field(IdentityConverter(np.int32), mask=0xF0)


class PortDIOSetPayload(AnonymousPayload[np.uint8]):
    """Represents the payload of the PortDIOSet register."""

    __value__: PortDigitalIOS = BitMask(enum=PortDigitalIOS)


class StartPulsePayload(StructPayload[np.uint16]):
    """Represents the payload of the StartPulse register."""

    digital_output: PwmPort = GroupMask(enum=PwmPort, mask=0xC00)
    pulse_width: np.uint16 = Field(IdentityConverter(np.uint16), mask=0x3FF)


class StartPulseTrainPayload(StructPayload[np.uint16], length=2):
    """Represents the payload of the StartPulseTrain register."""

    digital_output: PwmPort = GroupMask(enum=PwmPort, mask=0xC00)
    pulse_width: np.uint16 = Field(IdentityConverter(np.uint16), mask=0x3FF)
    frequency: np.uint8 = Field(
        IdentityConverter(np.uint8), mask=0xFF00, offset=1, default=np.uint8(1)
    )
    pulse_count: np.uint8 = Field(IdentityConverter(np.uint8), mask=0xFF, offset=1)


class EncoderModePayload(AnonymousPayload[np.uint8]):
    """Represents the payload of the EncoderMode register."""

    __value__: EncoderModeMask = GroupMask(enum=EncoderModeMask, mask=0xFF)


class DigitalInputs(RegisterU8):
    address: ClassVar[int] = 32


class AnalogData(RegisterBase[AnalogDataPayload]):
    address: ClassVar[int] = 33
    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class = AnalogDataPayload


class ComplexConfiguration(RegisterBase[ComplexConfigurationPayload]):
    address: ClassVar[int] = 34
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ComplexConfigurationPayload


class Version(RegisterBase[VersionPayload]):
    address: ClassVar[int] = 35
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = VersionPayload


class CustomPayload(RegisterBase[HarpVersion]):
    address: ClassVar[int] = 36
    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = CustomPayloadPayload


class CustomRawPayload(RegisterBase[HarpVersion]):
    address: ClassVar[int] = 37
    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = CustomRawPayloadPayload


class CustomMemberConverter(RegisterBase[CustomMemberConverterPayload]):
    address: ClassVar[int] = 38
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = CustomMemberConverterPayload


class BitmaskSplitter(RegisterBase[BitmaskSplitterPayload]):
    address: ClassVar[int] = 39
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = BitmaskSplitterPayload


class Counter0(RegisterS32):
    address: ClassVar[int] = 40


class PortDIOSet(RegisterBase[PortDigitalIOS]):
    address: ClassVar[int] = 41
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = PortDIOSetPayload


class PulseDOPort0(RegisterU16):
    address: ClassVar[int] = 42


class PulseDO0(RegisterU16):
    address: ClassVar[int] = 43


class StartPulse(RegisterBase[StartPulsePayload]):
    """Starts a PWM pulse."""

    address: ClassVar[int] = 100
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = StartPulsePayload


class StartPulseTrain(RegisterBase[StartPulseTrainPayload]):
    """Starts a PWM pulse train."""

    address: ClassVar[int] = 101
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = StartPulseTrainPayload


class EncoderMode(RegisterBase[EncoderModeMask]):
    """Configures the operation mode of the encoder."""

    address: ClassVar[int] = 103
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = EncoderModePayload


class Tests(Device):
    """A device driven by its own registers; the common Harp registers are merged
    in automatically. Registers are reached by name — ``Tests.registers.AnalogData``."""

    __REGISTERS__ = (
        DigitalInputs,
        AnalogData,
        ComplexConfiguration,
        Version,
        CustomPayload,
        CustomRawPayload,
        CustomMemberConverter,
        BitmaskSplitter,
        Counter0,
        PortDIOSet,
        PulseDOPort0,
        PulseDO0,
        StartPulse,
        StartPulseTrain,
        EncoderMode,
    )

    # Facade declaring the device's registers with real types so editors autocomplete
    # `device.registers.<Name>` and `read`/`write` infer the payload type. Never
    # instantiated — the namespace is built from `__REGISTERS__` by the base.
    class _Registers(CoreRegistersNamespace):
        DigitalInputs: type[DigitalInputs]
        AnalogData: type[AnalogData]
        ComplexConfiguration: type[ComplexConfiguration]
        Version: type[Version]
        CustomPayload: type[CustomPayload]
        CustomRawPayload: type[CustomRawPayload]
        CustomMemberConverter: type[CustomMemberConverter]
        BitmaskSplitter: type[BitmaskSplitter]
        Counter0: type[Counter0]
        PortDIOSet: type[PortDIOSet]
        PulseDOPort0: type[PulseDOPort0]
        PulseDO0: type[PulseDO0]
        StartPulse: type[StartPulse]
        StartPulseTrain: type[StartPulseTrain]
        EncoderMode: type[EncoderMode]

    registers: ClassVar[_Registers]
