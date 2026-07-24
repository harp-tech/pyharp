"""Acceptance tests: the device.yml coverage model in
``harp.benchmarks.register_models`` round-trips, and the new API behaviours
(offsets/gaps, masked overlap, single-member unwrap, strict enums) hold.
"""

import numpy as np
import pytest
from harp.data import payload_to_dataframe
from harp.protocol import HarpMessage, HarpVersion
from harp.benchmarks.register_models import (
    AnalogData,
    AnalogDataPayload,
    BitmaskSplitter,
    BitmaskSplitterPayload,
    ComplexConfiguration,
    ComplexConfigurationPayload,
    Counter0,
    CustomMemberConverter,
    CustomMemberConverterPayload,
    CustomPayload,
    CustomPayloadPayload,
    DigitalInputs,
    EncoderMode,
    EncoderModeMask,
    PortDIOSet,
    PortDIOSetPayload,
    PortDigitalIOS,
    PulseDO0,
    PulseDOPort0,
    PwmPort,
    StartPulse,
    StartPulsePayload,
    StartPulseTrain,
    StartPulseTrainPayload,
    Version,
    VersionPayload,
)


def _roundtrip(register, value):
    return register.parse(HarpMessage.parse(register.format(value)))


# ---------------------------------------------------------------------------
# Every register round-trips (format -> parse)
# ---------------------------------------------------------------------------


def test_scalar_registers_roundtrip():
    assert int(_roundtrip(DigitalInputs, np.uint8(0b1010))) == 0b1010
    assert int(_roundtrip(Counter0, np.int32(-100000))) == -100000
    assert int(_roundtrip(PulseDOPort0, np.uint16(5))) == 5
    assert int(_roundtrip(PulseDO0, np.uint16(9))) == 9


def test_analog_data_roundtrip():
    ad = AnalogDataPayload(
        Analog0=np.float32(1.0),
        Analog1=np.float32(2.0),
        Analog2=np.float32(3.0),
        Accelerometer=np.array([4, 5, 6], dtype=np.float32),
    )
    p = _roundtrip(AnalogData, ad)
    assert float(p.Analog0) == 1.0 and float(p.Analog2) == 3.0
    np.testing.assert_array_equal(p.Accelerometer, [4, 5, 6])
    assert AnalogDataPayload.dtype.itemsize == 24  # 6 floats


def test_version_roundtrip():
    ver = VersionPayload(
        ProtocolVersion=HarpVersion(2, 0, 0),
        FirmwareVersion=HarpVersion(1, 2, 3),
        HardwareVersion=HarpVersion(1, 0, 0),
        CoreId="abc",
        InterfaceHash=np.arange(20, dtype=np.uint8),
    )
    p = _roundtrip(Version, ver)
    assert p.ProtocolVersion == HarpVersion(2, 0, 0)
    assert p.CoreId == "abc"
    np.testing.assert_array_equal(p.InterfaceHash, np.arange(20))
    assert VersionPayload.dtype.itemsize == 32


def test_custom_member_converter_roundtrip():
    p = _roundtrip(
        CustomMemberConverter, CustomMemberConverterPayload(Header=np.uint8(7), Data=-1234)
    )
    assert int(p.Header) == 7 and int(p.Data) == -1234


def test_encoder_mode_roundtrip():
    # Single whole-register groupMask -> parse() unwraps to the bare enum.
    p = _roundtrip(EncoderMode, EncoderModeMask.Displacement)
    assert p == EncoderModeMask.Displacement
    assert isinstance(p, EncoderModeMask)


# ---------------------------------------------------------------------------
# Offsets + gaps (ComplexConfiguration)
# ---------------------------------------------------------------------------


def test_complex_configuration_gap_and_offsets():
    cc = ComplexConfigurationPayload(
        PwmPort=PwmPort.Pwm2,
        DutyCycle=np.float32(0.5),
        Frequency=np.float32(1000.0),
        EventsEnabled=True,
        Delta=np.uint32(42),
    )
    # itemsize from the register length (17), not the member extent.
    assert ComplexConfigurationPayload.dtype.itemsize == 17
    # bytes 1..3 are an uncovered gap, preserved on encode.
    assert cc.raw_payload.tobytes()[1:4] == b"\x00\x00\x00"
    # explicit byte offsets (base element = uint8, so element units == bytes).
    fields = ComplexConfigurationPayload.dtype.fields
    assert fields["DutyCycle"][1] == 4
    assert fields["Delta"][1] == 13

    p = _roundtrip(ComplexConfiguration, cc)
    assert p.PwmPort == PwmPort.Pwm2
    assert float(p.DutyCycle) == 0.5
    assert p.EventsEnabled is True
    assert int(p.Delta) == 42


# ---------------------------------------------------------------------------
# Masked overlap on one element (StartPulse / StartPulseTrain / BitmaskSplitter)
# ---------------------------------------------------------------------------


def test_start_pulse_overlapping_masks():
    # Two views of one U16 element share storage (one numpy field, itemsize 2).
    assert StartPulsePayload.dtype.itemsize == 2
    assert len(StartPulsePayload.dtype.names) == 1
    p = _roundtrip(
        StartPulse, StartPulsePayload(DigitalOutput=PwmPort.Pwm1, PulseWidth=np.uint16(300))
    )
    assert p.DigitalOutput == PwmPort.Pwm1
    assert int(p.PulseWidth) == 300


def test_start_pulse_train_two_words_and_default():
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
    assert StartPulseTrainPayload.dtype.itemsize == 4  # two U16 words
    # defaultValue: Frequency defaults to 1 when not provided.
    assert int(StartPulseTrainPayload(PulseCount=np.uint8(3)).Frequency) == 1


def test_bitmask_splitter_masked_ints():
    p = _roundtrip(BitmaskSplitter, BitmaskSplitterPayload(Low=0xA, High=0x5))
    assert int(p.Low) == 0xA and int(p.High) == 0x5
    assert p.raw_payload.tobytes() == bytes([0x5A])  # High packs into the top nibble


def test_port_dio_set_bitmask():
    # Single whole-register bitMask -> parse() unwraps to the bare IntFlag.
    p = _roundtrip(PortDIOSet, PortDigitalIOS.DIO0 | PortDigitalIOS.DIO3)
    assert p == PortDigitalIOS.DIO0 | PortDigitalIOS.DIO3
    assert PortDigitalIOS.DIO1 not in p
    assert PortDIOSetPayload.dtype.itemsize == 1


# ---------------------------------------------------------------------------
# Register-level interfaceType: single full-span member unwraps on parse
# ---------------------------------------------------------------------------


def test_custom_payload_single_member_unwrap():
    # Root payload: single __value__ view, unwrapped on parse.
    assert CustomPayloadPayload._single_member == "__value__"
    assert CustomPayloadPayload._root is True
    # U32[3] HarpVersion -> 12-byte buffer (3 x u32), same converter class.
    assert CustomPayloadPayload.dtype.itemsize == 12
    parsed = _roundtrip(CustomPayload, CustomPayloadPayload(HarpVersion(3, 1, 4)))
    assert isinstance(parsed, HarpVersion)
    assert parsed == HarpVersion(3, 1, 4)


# ---------------------------------------------------------------------------
# Strict enums: an out-of-range masked code raises
# ---------------------------------------------------------------------------


def test_strict_enum_raises_on_unknown_code():
    # StartPulse.DigitalOutput is a 2-bit field; code 0b11 has no PwmPort member.
    raw = np.array(0b11 << 10, dtype=np.uint16).tobytes()
    payload = StartPulsePayload.from_buffer(raw)
    with pytest.raises(ValueError):
        _ = payload.DigitalOutput


# ---------------------------------------------------------------------------
# to_dataframe over masked + offset payloads
# ---------------------------------------------------------------------------


def test_complex_configuration_to_dataframe():
    cc = ComplexConfigurationPayload(
        PwmPort=PwmPort.Pwm2,
        DutyCycle=np.float32(0.5),
        Frequency=np.float32(1.0),
        EventsEnabled=True,
        Delta=np.uint32(42),
    )
    batch = ComplexConfigurationPayload.from_buffer(cc.raw_payload.tobytes() * 2)
    df = payload_to_dataframe(batch)
    assert len(df) == 2
    assert list(df["PwmPort"]) == ["Pwm2", "Pwm2"]
    np.testing.assert_array_equal(df["Delta"], [42, 42])
