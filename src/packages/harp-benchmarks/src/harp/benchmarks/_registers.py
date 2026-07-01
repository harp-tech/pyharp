"""Shared benchmark fixtures: every register from ``harp.benchmarks.register_models``
paired with a representative sample value.

Both ``generate.py`` (writes the .bin corpora) and ``benchmark.py`` (times parsing)
import :data:`BENCHMARK_REGISTERS` from here so the two stay in lock-step: the value
used to *format* each frame is the same one whose parsed shape we benchmark.

The sample values mirror ``register_models.main()``'s round-trip fixtures — they
exercise the full spread of payload shapes the Harp protocol allows (trivial
scalars, struct payloads with byte gaps, masked sub-fields, custom converters,
enum/flag single-member unwrap).

All generated artifacts live under ``./benchmark`` in the current working directory.
"""

from pathlib import Path
from typing import Any, NamedTuple

import numpy as np

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
    CustomRawPayload,
    DigitalInputs,
    EncoderMode,
    EncoderModeMask,
    PortDigitalIOS,
    PortDIOSet,
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
from harp.protocol import HarpVersion, RegisterBase

ARTIFACTS_DIR = Path("benchmark").resolve()
DATA_DIR = ARTIFACTS_DIR / "data"
REPORT_PATH = ARTIFACTS_DIR / "report.md"


class BenchmarkedRegister(NamedTuple):
    """A register under benchmark together with a value that ``format()`` accepts."""

    name: str
    register: type[RegisterBase[Any]]
    value: Any

    @property
    def address(self) -> int:
        return self.register.address

    @property
    def filename(self) -> str:
        return f"{self.name}_{self.address}.bin"


def _build() -> list[BenchmarkedRegister]:
    return [
        BenchmarkedRegister("DigitalInputs", DigitalInputs, np.uint8(0b1010)),
        BenchmarkedRegister(
            "AnalogData",
            AnalogData,
            AnalogDataPayload(
                Analog0=np.float32(1.0),
                Analog1=np.float32(2.0),
                Analog2=np.float32(3.0),
                Accelerometer=np.array([4, 5, 6], dtype=np.float32),
            ),
        ),
        BenchmarkedRegister(
            "ComplexConfiguration",
            ComplexConfiguration,
            ComplexConfigurationPayload(
                PwmPort=PwmPort.Pwm2,
                DutyCycle=np.float32(0.5),
                Frequency=np.float32(1000.0),
                EventsEnabled=True,
                Delta=np.uint32(42),
            ),
        ),
        BenchmarkedRegister(
            "Version",
            Version,
            VersionPayload(
                ProtocolVersion=HarpVersion(2, 0, 0),
                FirmwareVersion=HarpVersion(1, 2, 3),
                HardwareVersion=HarpVersion(1, 0, 0),
                CoreId="abc",
                InterfaceHash=np.arange(20, dtype=np.uint8),
            ),
        ),
        BenchmarkedRegister("CustomPayload", CustomPayload, HarpVersion(3, 1, 4)),
        BenchmarkedRegister("CustomRawPayload", CustomRawPayload, HarpVersion(0, 0, 1)),
        BenchmarkedRegister(
            "CustomMemberConverter",
            CustomMemberConverter,
            CustomMemberConverterPayload(Header=np.uint8(7), Data=-1234),
        ),
        BenchmarkedRegister(
            "BitmaskSplitter",
            BitmaskSplitter,
            BitmaskSplitterPayload(Low=np.int32(0xA), High=np.int32(0x5)),
        ),
        BenchmarkedRegister("Counter0", Counter0, np.int32(-100000)),
        BenchmarkedRegister(
            "PortDIOSet",
            PortDIOSet,
            PortDigitalIOS.DIO0 | PortDigitalIOS.DIO3,
        ),
        BenchmarkedRegister("PulseDOPort0", PulseDOPort0, np.uint16(5)),
        BenchmarkedRegister("PulseDO0", PulseDO0, np.uint16(9)),
        BenchmarkedRegister(
            "StartPulse",
            StartPulse,
            StartPulsePayload(DigitalOutput=PwmPort.Pwm1, PulseWidth=np.uint16(300)),
        ),
        BenchmarkedRegister(
            "StartPulseTrain",
            StartPulseTrain,
            StartPulseTrainPayload(
                DigitalOutput=PwmPort.Pwm1,
                PulseWidth=np.uint16(300),
                Frequency=np.uint8(200),
                PulseCount=np.uint8(50),
            ),
        ),
        BenchmarkedRegister("EncoderMode", EncoderMode, EncoderModeMask.Displacement),
    ]


BENCHMARK_REGISTERS: list[BenchmarkedRegister] = _build()
