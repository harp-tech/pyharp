"""Reference models for every register in the canonical generator test device
(``harp-tech/generators`` -> ``tests/Metadata/device.yml``), built with the
``harp.protocol`` public API.

These act as fixtures for ``test_register_modeling.py`` and demonstrate that the
API can express every payload shape the Harp protocol allows (gaps, overlaps,
masks, reinterpreted sub-regions, custom domain types) before building a
spec->code generator. Run it directly to round-trip every register::

    uv run python -m tests.protocol.register_models

Design (see notes/payload_api_redesign.md):

* A payload is a flat buffer of base-``type`` elements; each member is a typed
  view ``(offset, mask, converter)``. ``offset`` is in base-element units.
* ``Converter`` instances operate on their own byte layout and are independent of
  the register element type (custom codecs read raw ``uint8`` sub-arrays), so the
  same ``HarpVersionConverter`` works under a U8 or a U32 register.
* Masked sub-fields use ``GroupMask`` (enum) or ``Field(converter=..., mask=...)``
  (numeric); the right-shift is derived from the mask's trailing zeros.
* The register ``length`` (base elements) fixes ``itemsize`` so byte gaps survive.
* Enum decoding is strict: an out-of-range code raises.
"""

import enum
from typing import Any, ClassVar

import numpy as np
from numpy.typing import NDArray

from harp.protocol import (
    AnonymousPayload,
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

# ===========================================================================
# device.yml bitMasks + groupMasks
# ===========================================================================


class PortDigitalIOS(enum.IntFlag):
    """device.yml bitMasks.PortDigitalIOS (bits up to 0x800 — see PortDIOSet)."""

    DIO0 = 0x1
    DIO1 = 0x2
    DIO2 = 0x4
    DIO3 = 0x8
    DIPort0 = 0x100
    TestDIPort1 = 0x200
    SupplyPort0 = 0x400
    PortDIO1 = 0x800


class PwmPort(enum.IntEnum):
    """device.yml groupMasks.PwmPort (note Pwm3 = 0xA)."""

    Pwm0 = 0x1
    Pwm1 = 0x2
    Pwm2 = 0x4
    Pwm3 = 0xA


class EncoderModeMask(enum.IntEnum):
    """device.yml groupMasks.EncoderModeMask."""

    Position = 0x0
    Displacement = 0x1


# ===========================================================================
# Custom interfaceType converters — byte-based, register-element-agnostic.
# ===========================================================================


class BytesToIntConverter(Converter[int]):
    """N raw bytes (little-endian) <-> Python int. Models ``interfaceType: int`` over a sub-array."""

    def __init__(self, length: int, *, signed: bool = False) -> None:
        self._length = length
        self._signed = signed
        self.dtype = np.dtype((np.uint8, (length,)))

    def decode_scalar(self, view: np.generic) -> int:
        return int.from_bytes(bytes(np.asarray(view).tolist()), "little", signed=self._signed)

    def decode_batch(self, view: NDArray[np.generic]) -> Any:
        return np.array(
            [
                int.from_bytes(bytes(np.asarray(r).tolist()), "little", signed=self._signed)
                for r in np.atleast_2d(view)
            ],
            dtype=object,
        )

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
# 33  AnalogData : Float[6], Event — named sub-views + a 3-float sub-array.
# ===========================================================================


class AnalogDataPayload(StructPayload[np.float32], length=6):
    Analog0: np.float32 = Field(IdentityConverter(np.float32), offset=0)
    Analog1: np.float32 = Field(IdentityConverter(np.float32), offset=1)
    Analog2: np.float32 = Field(IdentityConverter(np.float32), offset=2)
    Accelerometer: NDArray[np.float32] = Field(
        IdentityConverter(np.dtype((np.float32, (3,)))), offset=3
    )


class AnalogData(RegisterBase[AnalogDataPayload]):
    address: ClassVar[int] = 33
    payload_type: ClassVar[PayloadType] = PayloadType.Float
    payload_class = AnalogDataPayload


# ===========================================================================
# 34  ComplexConfiguration : U8[17], Write — byte gap at bytes 1..3.
# ===========================================================================


class ComplexConfigurationPayload(StructPayload[np.uint8], length=17):
    PwmPort: "PwmPort" = GroupMask(
        enum=PwmPort, mask=0xFF, offset=0
    )  # quoted: member name shadows enum type
    DutyCycle: np.float32 = Field(IdentityConverter(np.float32), offset=4)
    Frequency: np.float32 = Field(IdentityConverter(np.float32), offset=8)
    EventsEnabled: bool = Field(BoolConverter(), offset=12)
    Delta: np.uint32 = Field(IdentityConverter(np.uint32), offset=13)


class ComplexConfiguration(RegisterBase[ComplexConfigurationPayload]):
    address: ClassVar[int] = 34
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = ComplexConfigurationPayload


# ===========================================================================
# 35  Version : U8[32], Event — HarpVersion x3 (3-byte) + string + raw hash.
# ===========================================================================


class VersionPayload(StructPayload[np.uint8], length=32):
    ProtocolVersion: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=0)
    FirmwareVersion: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=3)
    HardwareVersion: HarpVersion = Field(HarpVersionConverter(np.uint8), offset=6)
    CoreId: str = Field(StringConverter(3), offset=9)
    InterfaceHash: NDArray[np.uint8] = Field(
        IdentityConverter(np.dtype((np.uint8, (20,)))), offset=12
    )


class Version(RegisterBase[VersionPayload]):
    address: ClassVar[int] = 35
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = VersionPayload


# ===========================================================================
# 36 / 37  CustomPayload / CustomRawPayload : U32[3] — register-level
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
# 38  CustomMemberConverter : U8[3], Read — Header (uint8) + Data (2 bytes -> int).
# ===========================================================================


class CustomMemberConverterPayload(StructPayload[np.uint8], length=3):
    Header: np.uint8 = Field(IdentityConverter(np.uint8))
    Data: int = Field(BytesToIntConverter(2, signed=True), offset=1)


class CustomMemberConverter(RegisterBase[CustomMemberConverterPayload]):
    address: ClassVar[int] = 38
    payload_type: ClassVar[PayloadType] = PayloadType.U8
    payload_class = CustomMemberConverterPayload


# ===========================================================================
# 39  BitmaskSplitter : U8, Write — Low (mask 0xF, int) + High (mask 0xF0, int).
# ===========================================================================


class BitmaskSplitterPayload(StructPayload[np.uint8]):
    Low: np.int32 = Field(IdentityConverter(np.int32), mask=0x0F)
    High: np.int32 = Field(IdentityConverter(np.int32), mask=0xF0)


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
# 41  PortDIOSet : U8, Write — bitMask PortDigitalIOS. A single BitMask over the
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
# 100  StartPulse : U16, Write — two overlapping views of one word.
# ===========================================================================


class StartPulsePayload(StructPayload[np.uint16]):
    DigitalOutput: PwmPort = GroupMask(enum=PwmPort, mask=0xC00)
    PulseWidth: np.uint16 = Field(IdentityConverter(np.uint16), mask=0x3FF)


class StartPulse(RegisterBase[StartPulsePayload]):
    address: ClassVar[int] = 100
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = StartPulsePayload


# ===========================================================================
# 101  StartPulseTrain : U16[2], Write — 4 masked members across two words.
# ===========================================================================


class StartPulseTrainPayload(StructPayload[np.uint16], length=2):
    DigitalOutput: PwmPort = GroupMask(enum=PwmPort, mask=0xC00, offset=0)
    PulseWidth: np.uint16 = Field(IdentityConverter(np.uint16), mask=0x3FF, offset=0)
    Frequency: np.uint8 = Field(
        IdentityConverter(np.uint8), mask=0xFF00, offset=1, default=np.uint8(1)
    )
    PulseCount: np.uint8 = Field(IdentityConverter(np.uint8), mask=0xFF, offset=1)


class StartPulseTrain(RegisterBase[StartPulseTrainPayload]):
    address: ClassVar[int] = 101
    payload_type: ClassVar[PayloadType] = PayloadType.U16
    payload_class = StartPulseTrainPayload


# ===========================================================================
# 103  EncoderMode : U8, Write — whole-register groupMask.
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
        Analog0=np.float32(1.0),
        Analog1=np.float32(2.0),
        Analog2=np.float32(3.0),
        Accelerometer=np.array([4, 5, 6], dtype=np.float32),
    )
    p = _roundtrip(AnalogData, ad)
    assert float(p.Analog0) == 1.0 and float(p.Analog2) == 3.0
    np.testing.assert_array_equal(p.Accelerometer, [4, 5, 6])
    print(f"AnalogData               OK  ({AnalogDataPayload.dtype.itemsize} bytes)")

    cc = ComplexConfigurationPayload(
        PwmPort=PwmPort.Pwm2,
        DutyCycle=np.float32(0.5),
        Frequency=np.float32(1000.0),
        EventsEnabled=True,
        Delta=np.uint32(42),
    )
    p = _roundtrip(ComplexConfiguration, cc)
    assert p.PwmPort == PwmPort.Pwm2 and p.EventsEnabled is True and int(p.Delta) == 42
    assert float(p.DutyCycle) == 0.5
    assert ComplexConfigurationPayload.dtype.itemsize == 17
    assert cc.raw_payload.tobytes()[1:4] == b"\x00\x00\x00"
    print(
        f"ComplexConfiguration     OK  ({ComplexConfigurationPayload.dtype.itemsize} bytes, gap 1..3)"
    )

    ver = VersionPayload(
        ProtocolVersion=HarpVersion(2, 0, 0),
        FirmwareVersion=HarpVersion(1, 2, 3),
        HardwareVersion=HarpVersion(1, 0, 0),
        CoreId="abc",
        InterfaceHash=np.arange(20, dtype=np.uint8),
    )
    p = _roundtrip(Version, ver)
    assert p.ProtocolVersion == HarpVersion(2, 0, 0) and p.CoreId == "abc"
    np.testing.assert_array_equal(p.InterfaceHash, np.arange(20))
    print(f"Version                  OK  ({VersionPayload.dtype.itemsize} bytes)")

    p = _roundtrip(CustomPayload, CustomPayloadPayload(value=HarpVersion(3, 1, 4)))
    assert p == HarpVersion(3, 1, 4)  # single-member unwrap -> bare HarpVersion
    p = _roundtrip(CustomRawPayload, CustomRawPayloadPayload(value=HarpVersion(0, 0, 1)))
    assert p == HarpVersion(0, 0, 1)
    print("CustomPayload/RawPayload OK  (single-member unwrap)")

    p = _roundtrip(
        CustomMemberConverter, CustomMemberConverterPayload(Header=np.uint8(7), Data=-1234)
    )
    assert int(p.Header) == 7 and int(p.Data) == -1234
    print("CustomMemberConverter    OK")

    p = _roundtrip(BitmaskSplitter, BitmaskSplitterPayload(Low=0xA, High=0x5))
    assert int(p.Low) == 0xA and int(p.High) == 0x5
    assert p.raw_payload.tobytes() == bytes([0x5A])
    print("BitmaskSplitter          OK")

    assert int(_roundtrip(Counter0, np.int32(-100000))) == -100000
    print("Counter0                 OK")

    p = _roundtrip(PortDIOSet, PortDigitalIOS.DIO0 | PortDigitalIOS.DIO3)
    assert p == PortDigitalIOS.DIO0 | PortDigitalIOS.DIO3  # single-member unwrap
    assert PortDigitalIOS.DIO1 not in p
    assert PortDIOSetPayload.dtype.itemsize == 1
    print("PortDIOSet               OK")

    assert int(_roundtrip(PulseDOPort0, np.uint16(5))) == 5
    assert int(_roundtrip(PulseDO0, np.uint16(9))) == 9
    print("PulseDOPort0 / PulseDO0  OK")

    p = _roundtrip(
        StartPulse, StartPulsePayload(DigitalOutput=PwmPort.Pwm1, PulseWidth=np.uint16(300))
    )
    assert p.DigitalOutput == PwmPort.Pwm1 and int(p.PulseWidth) == 300
    print("StartPulse               OK")

    p = _roundtrip(
        StartPulseTrain,
        StartPulseTrainPayload(
            DigitalOutput=PwmPort.Pwm1,
            PulseWidth=np.uint16(300),
            Frequency=np.uint8(200),
            PulseCount=np.uint8(50),
        ),
    )
    assert p.DigitalOutput == PwmPort.Pwm1 and int(p.PulseWidth) == 300
    assert int(p.Frequency) == 200 and int(p.PulseCount) == 50
    assert StartPulseTrainPayload.dtype.itemsize == 4
    assert int(StartPulseTrainPayload(PulseCount=np.uint8(3)).Frequency) == 1  # defaultValue
    print("StartPulseTrain          OK  (4 masked members, 2 words, default Frequency=1)")

    p = _roundtrip(EncoderMode, EncoderModeMask.Displacement)
    assert p == EncoderModeMask.Displacement  # single-member unwrap
    print("EncoderMode              OK")

    print("\nAll device.yml registers round-trip cleanly.")


if __name__ == "__main__":
    main()
