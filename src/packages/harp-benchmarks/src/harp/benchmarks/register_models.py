import enum
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from harp.protocol import (
    AnonymousPayload,
    ArrayConverter,
    BitMask,
    BoolConverter,
    Converter,
    Field,
    GroupMask,
    HarpMessage,
    IdentityConverter,
    HarpVersionConverter,
    HarpVersion,
    PayloadType,
    RegisterBase,
    RegisterS32,
    RegisterU8,
    RegisterU16,
    StringConverter,
    StructPayload,
)

# This file targets the device.yml here
# https://raw.githubusercontent.com/harp-tech/generators/refs/heads/main/tests/Metadata/device.yml


# ===========================================================================
# device.yml bitMasks + groupMasks
# ===========================================================================


class PortDigitalIOS(enum.IntFlag):
    """device.yml bitMasks.PortDigitalIOS, with bits up to 0x800. See PortDIOSet."""

    DIO0 = 0x1
    DIO1 = 0x2
    DIO2 = 0x4
    DIO3 = 0x8
    DI_PORT0 = 0x100
    TEST_DI_PORT1 = 0x200
    SUPPLY_PORT0 = 0x400
    PORT_DIO1 = 0x800


class PwmPort(enum.IntEnum):
    """device.yml groupMasks.PwmPort (note PWM3 = 0xA)."""

    PWM0 = 0x1
    PWM1 = 0x2
    PWM2 = 0x4
    PWM3 = 0xA


class EncoderModeMask(enum.IntEnum):
    """device.yml groupMasks.EncoderModeMask."""

    POSITION = 0x0
    DISPLACEMENT = 0x1


# ===========================================================================
# Custom interfaceType converters, byte-based and register-element-agnostic.
# ===========================================================================


class BytesToIntConverter(Converter[int]):
    """N raw bytes (little-endian) <-> Python int. Models ``interfaceType: int`` over a sub-array."""

    def __init__(self, length: int, *, signed: bool = False) -> None:
        self._length = length
        self._signed = signed
        endian = "<" if length > 1 else ""
        kind = "i" if signed else "u"
        self._native = IdentityConverter(f"{endian}{kind}{length}")
        self.dtype = np.dtype((np.uint8, (length,)))

    def decode_scalar(self, view: np.generic) -> int:
        return int.from_bytes(bytes(np.asarray(view).tolist()), "little", signed=self._signed)

    def decode_batch(self, view: NDArray[np.generic]) -> Any:
        rows = np.atleast_2d(view).reshape(-1, self._length)
        return self._native.decode_batch(rows.view(self._native.dtype).reshape(-1))

    def encode_into(self, view: NDArray[np.generic], value: int) -> None:
        view[...] = np.frombuffer(
            int(value).to_bytes(self._length, "little", signed=self._signed), dtype=np.uint8
        )


# ===========================================================================
# 32  DigitalInputs : U8, Event  -> trivial scalar register
# ===========================================================================


class DigitalInputs(RegisterU8):
    address: ClassVar[int] = 32


# ===========================================================================
# 33  AnalogData : Float[6], Event. Named sub-views plus a 3-float sub-array.
# ===========================================================================


class AnalogDataPayload(StructPayload[np.float32], length=6):
    analog0: np.float32 = Field(IdentityConverter(np.float32), offset=0)
    analog1: np.float32 = Field(IdentityConverter(np.float32), offset=1)
    analog2: np.float32 = Field(IdentityConverter(np.float32), offset=2)
    accelerometer: NDArray[np.float32] = Field(ArrayConverter(np.float32, 3), offset=3)


class AnalogData(RegisterBase[AnalogDataPayload]):
    address: ClassVar[int] = 33
    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class = AnalogDataPayload


# ===========================================================================
# 34  ComplexConfiguration : U8[17], Write. Byte gap at bytes 1..3.
# ===========================================================================


class ComplexConfigurationPayload(StructPayload[np.uint8], length=17):
    pwm_port: PwmPort = GroupMask(enum=PwmPort, mask=0xFF, offset=0)
    duty_cycle: np.float32 = Field(IdentityConverter(np.float32), offset=4)
    frequency: np.float32 = Field(IdentityConverter(np.float32), offset=8)
    events_enabled: bool = Field(BoolConverter(), offset=12)
    delta: np.uint32 = Field(IdentityConverter(np.uint32), offset=13)


class ComplexConfiguration(RegisterBase[ComplexConfigurationPayload]):
    address: ClassVar[int] = 34
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ComplexConfigurationPayload


# ===========================================================================
# 35  Version : U8[32], Event. HarpVersion x3 (3-byte), string, and raw hash.
# ===========================================================================


class VersionPayload(StructPayload[np.uint8], length=32):
    protocol_version: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=0)
    firmware_version: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=3)
    hardware_version: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=6)
    core_id: str = Field(StringConverter(3), offset=9)
    interface_hash: NDArray[np.uint8] = Field(ArrayConverter(np.uint8, 20), offset=12)


class Version(RegisterBase[VersionPayload]):
    address: ClassVar[int] = 35
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = VersionPayload


# ===========================================================================
# 36 / 37  CustomPayload / CustomRawPayload : U32[3]. Register-level
#          interfaceType HarpVersion. Single full-span member -> parse() unwraps.
# ===========================================================================


class CustomPayloadPayload(AnonymousPayload[np.uint32]):
    __value__: HarpVersion = Field(HarpVersionConverter(np.uint32))


class CustomPayload(RegisterBase[HarpVersion]):
    address: ClassVar[int] = 36
    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = CustomPayloadPayload


class CustomRawPayloadPayload(AnonymousPayload[np.uint32]):
    __value__: HarpVersion = Field(HarpVersionConverter(np.uint32))


class CustomRawPayload(RegisterBase[HarpVersion]):
    address: ClassVar[int] = 37
    payload_type: ClassVar[PayloadType] = PayloadType.U32
    payload_class = CustomRawPayloadPayload


# ===========================================================================
# 38  CustomMemberConverter : U8[3], Read. Header (uint8) and Data (2 bytes -> int).
# ===========================================================================


class CustomMemberConverterPayload(StructPayload[np.uint8], length=3):
    header: np.uint8 = Field(IdentityConverter(np.uint8))
    data: int = Field(BytesToIntConverter(2, signed=True), offset=1)


class CustomMemberConverter(RegisterBase[CustomMemberConverterPayload]):
    address: ClassVar[int] = 38
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = CustomMemberConverterPayload


# ===========================================================================
# 39  BitmaskSplitter : U8, Write. Low (mask 0xF, int) and High (mask 0xF0, int).
# ===========================================================================


class BitmaskSplitterPayload(StructPayload[np.uint8]):
    low: np.int32 = Field(IdentityConverter(np.int32), mask=0x0F)
    high: np.int32 = Field(IdentityConverter(np.int32), mask=0xF0)


class BitmaskSplitter(RegisterBase[BitmaskSplitterPayload]):
    address: ClassVar[int] = 39
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = BitmaskSplitterPayload


# ===========================================================================
# 40  Counter0 : S32, Event  -> trivial scalar register
# ===========================================================================


class Counter0(RegisterS32):
    address: ClassVar[int] = 40


# ===========================================================================
# 41  PortDIOSet : U8, Write. bitMask PortDigitalIOS, a single BitMask over the
#     whole byte; bits >= 0x100 can't fit a U8 so they are dropped. Single-member
#     -> parse() unwraps to a bare PortDigitalIOS.
# ===========================================================================


class PortDIOSetPayload(AnonymousPayload[np.uint8]):
    __value__: PortDigitalIOS = BitMask(enum=PortDigitalIOS, mask=0xFF)


class PortDIOSet(RegisterBase[PortDigitalIOS]):
    address: ClassVar[int] = 41
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = PortDIOSetPayload


# ===========================================================================
# 42 / 43  PulseDOPort0 / PulseDO0 : U16, Write
# ===========================================================================


class PulseDOPort0(RegisterU16):
    address: ClassVar[int] = 42


class PulseDO0(RegisterU16):
    address: ClassVar[int] = 43


# ===========================================================================
# 100  StartPulse : U16, Write. Two overlapping views of one word.
# ===========================================================================


class StartPulsePayload(StructPayload[np.uint16]):
    digital_output: PwmPort = GroupMask(enum=PwmPort, mask=0xC00)
    pulse_width: np.uint16 = Field(IdentityConverter(np.uint16), mask=0x3FF)


class StartPulse(RegisterBase[StartPulsePayload]):
    address: ClassVar[int] = 100
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = StartPulsePayload


# ===========================================================================
# 101  StartPulseTrain : U16[2], Write. 4 masked members across two words.
# ===========================================================================


class StartPulseTrainPayload(StructPayload[np.uint16], length=2):
    digital_output: PwmPort = GroupMask(enum=PwmPort, mask=0xC00, offset=0)
    pulse_width: np.uint16 = Field(IdentityConverter(np.uint16), mask=0x3FF, offset=0)
    frequency: np.uint8 = Field(
        IdentityConverter(np.uint8), mask=0xFF00, offset=1, default=np.uint8(1)
    )
    pulse_count: np.uint8 = Field(IdentityConverter(np.uint8), mask=0xFF, offset=1)


class StartPulseTrain(RegisterBase[StartPulseTrainPayload]):
    address: ClassVar[int] = 101
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = StartPulseTrainPayload


# ===========================================================================
# 103  EncoderMode : U8, Write. Whole-register groupMask.
# ===========================================================================


class EncoderModePayload(AnonymousPayload[np.uint8]):
    __value__: EncoderModeMask = GroupMask(enum=EncoderModeMask, mask=0xFF)


class EncoderMode(RegisterBase[EncoderModeMask]):
    address: ClassVar[int] = 103
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = EncoderModePayload


# ===========================================================================
# Round-trip smoke test
# ===========================================================================


def _roundtrip(register: type[RegisterBase[Any]], value: Any) -> Any:
    frame = register.format(value)
    return register.parse(HarpMessage.parse(frame))


def main() -> None:  # pragma: no cover - manual exploration entry point
    print("=== Every device.yml register, format -> parse round-trip ===\n")

    assert _roundtrip(DigitalInputs, np.uint8(0b1010)) == 0b1010
    print("DigitalInputs            OK")

    ad = AnalogDataPayload(
        analog0=np.float32(1.0),
        analog1=np.float32(2.0),
        analog2=np.float32(3.0),
        accelerometer=np.array([4, 5, 6], dtype=np.float32),
    )
    p = _roundtrip(AnalogData, ad)
    assert float(p.analog0) == 1.0 and float(p.analog2) == 3.0
    np.testing.assert_array_equal(p.accelerometer, [4, 5, 6])
    print(f"AnalogData               OK  ({AnalogDataPayload.payload_dtype.itemsize} bytes)")

    cc = ComplexConfigurationPayload(
        pwm_port=PwmPort.PWM2,
        duty_cycle=np.float32(0.5),
        frequency=np.float32(1000.0),
        events_enabled=True,
        delta=np.uint32(42),
    )
    p = _roundtrip(ComplexConfiguration, cc)
    assert p.pwm_port == PwmPort.PWM2 and p.events_enabled is True and int(p.delta) == 42
    assert float(p.duty_cycle) == 0.5
    assert ComplexConfigurationPayload.payload_dtype.itemsize == 17
    assert cc.payload_array.tobytes()[1:4] == b"\x00\x00\x00"
    print(
        f"ComplexConfiguration     OK  ({ComplexConfigurationPayload.payload_dtype.itemsize} bytes, gap 1..3)"
    )

    ver = VersionPayload(
        protocol_version=HarpVersion(2, 0, 0),
        firmware_version=HarpVersion(1, 2, 3),
        hardware_version=HarpVersion(1, 0, 0),
        core_id="abc",
        interface_hash=np.arange(20, dtype=np.uint8),
    )
    p = _roundtrip(Version, ver)
    assert p.protocol_version == HarpVersion(2, 0, 0) and p.core_id == "abc"
    np.testing.assert_array_equal(p.interface_hash, np.arange(20))
    print(f"Version                  OK  ({VersionPayload.payload_dtype.itemsize} bytes)")

    p = _roundtrip(CustomPayload, HarpVersion(3, 1, 4))
    assert p == HarpVersion(3, 1, 4)  # single-member unwrap -> bare HarpVersion
    p = _roundtrip(CustomRawPayload, HarpVersion(0, 0, 1))
    assert p == HarpVersion(0, 0, 1)
    print("CustomPayload/RawPayload OK  (single-member unwrap)")

    p = _roundtrip(
        CustomMemberConverter, CustomMemberConverterPayload(header=np.uint8(7), data=-1234)
    )
    assert int(p.header) == 7 and int(p.data) == -1234
    print("CustomMemberConverter    OK")

    p = _roundtrip(BitmaskSplitter, BitmaskSplitterPayload(low=np.int32(0xA), high=np.int32(0x5)))
    assert int(p.low) == 0xA and int(p.high) == 0x5
    assert p.payload_array.tobytes() == bytes([0x5A])
    print("BitmaskSplitter          OK")

    assert int(_roundtrip(Counter0, np.int32(-100000))) == -100000
    print("Counter0                 OK")

    p = _roundtrip(PortDIOSet, PortDigitalIOS.DIO0 | PortDigitalIOS.DIO3)
    assert p == PortDigitalIOS.DIO0 | PortDigitalIOS.DIO3  # single-member unwrap
    assert PortDigitalIOS.DIO1 not in p
    assert PortDIOSetPayload.payload_dtype.itemsize == 1
    print("PortDIOSet               OK")

    assert int(_roundtrip(PulseDOPort0, np.uint16(5))) == 5
    assert int(_roundtrip(PulseDO0, np.uint16(9))) == 9
    print("PulseDOPort0 / PulseDO0  OK")

    p = _roundtrip(
        StartPulse, StartPulsePayload(digital_output=PwmPort.PWM1, pulse_width=np.uint16(300))
    )
    assert p.digital_output == PwmPort.PWM1 and int(p.pulse_width) == 300
    print("StartPulse               OK")

    p = _roundtrip(
        StartPulseTrain,
        StartPulseTrainPayload(
            digital_output=PwmPort.PWM1,
            pulse_width=np.uint16(300),
            frequency=np.uint8(200),
            pulse_count=np.uint8(50),
        ),
    )
    assert p.digital_output == PwmPort.PWM1 and int(p.pulse_width) == 300
    assert int(p.frequency) == 200 and int(p.pulse_count) == 50
    assert StartPulseTrainPayload.payload_dtype.itemsize == 4
    partial = StartPulseTrainPayload(
        digital_output=PwmPort.PWM0, pulse_width=np.uint16(0), pulse_count=np.uint8(3)
    )
    assert int(partial.frequency) == 1  # defaultValue
    print("StartPulseTrain          OK  (4 masked members, 2 words, default frequency=1)")

    p = _roundtrip(EncoderMode, EncoderModeMask.DISPLACEMENT)
    assert p == EncoderModeMask.DISPLACEMENT  # single-member unwrap
    print("EncoderMode              OK")

    print("\nAll device.yml registers round-trip cleanly.")


if __name__ == "__main__":
    main()
