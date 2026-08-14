"""Shared benchmark fixtures: every register from ``harp.benchmarks.register_models``
paired with whether its frames carry a timestamp.

Both ``generate.py`` (writes the .bin corpora) and ``benchmark.py`` (times parsing)
import :data:`BENCHMARK_REGISTERS` from here so the two stay in lock-step. Payloads
are synthesized as random bytes per frame at generation time (see ``generate.py``),
so no sample values live here, only the register class and its frame shape.

All generated artifacts live under ``./benchmark`` in the current working directory.
"""

from pathlib import Path
from typing import Any, NamedTuple

from harp.benchmarks.register_models import (
    AnalogData,
    BitmaskSplitter,
    ComplexConfiguration,
    Counter0,
    CustomMemberConverter,
    CustomPayload,
    CustomRawPayload,
    DigitalInputs,
    EncoderMode,
    PortDIOSet,
    PulseDO0,
    PulseDOPort0,
    StartPulse,
    StartPulseTrain,
    Version,
)
from harp.protocol import RegisterBase

ARTIFACTS_DIR = Path("benchmark").resolve()
DATA_DIR = ARTIFACTS_DIR / "data"
REPORT_PATH = ARTIFACTS_DIR / "report.md"


class BenchmarkedRegister(NamedTuple):
    """A register under benchmark, with whether its corpus frames are timestamped."""

    name: str
    register: type[RegisterBase[Any]]
    timestamped: bool = True

    @property
    def address(self) -> int:
        return self.register.address

    @property
    def filename(self) -> str:
        return f"{self.name}_{self.address}.bin"


def _base_registers() -> list[BenchmarkedRegister]:
    """One timestamped fixture per register, from which :func:`_build` derives the untimestamped twin.

    The set spans the full spread of payload shapes the Harp protocol allows: trivial
    scalars, struct payloads with byte gaps, masked sub-fields, custom converters, and
    enum/flag single-member unwrap.
    """
    return [
        BenchmarkedRegister("DigitalInputs", DigitalInputs),
        BenchmarkedRegister("AnalogData", AnalogData),
        BenchmarkedRegister("ComplexConfiguration", ComplexConfiguration),
        BenchmarkedRegister("Version", Version),
        BenchmarkedRegister("CustomPayload", CustomPayload),
        BenchmarkedRegister("CustomRawPayload", CustomRawPayload),
        BenchmarkedRegister("CustomMemberConverter", CustomMemberConverter),
        BenchmarkedRegister("BitmaskSplitter", BitmaskSplitter),
        BenchmarkedRegister("Counter0", Counter0),
        BenchmarkedRegister("PortDIOSet", PortDIOSet),
        BenchmarkedRegister("PulseDOPort0", PulseDOPort0),
        BenchmarkedRegister("PulseDO0", PulseDO0),
        BenchmarkedRegister("StartPulse", StartPulse),
        BenchmarkedRegister("StartPulseTrain", StartPulseTrain),
        BenchmarkedRegister("EncoderMode", EncoderMode),
    ]


def _build() -> list[BenchmarkedRegister]:
    """Expand every base fixture into a timestamped + untimestamped pair.

    ``parse_bulk`` detects timestamping from the wire format at runtime (not
    statically), so every register needs a corpus of each shape to exercise both
    the eager (``timestamps`` present) and ``None`` decode paths.
    """
    registers: list[BenchmarkedRegister] = []
    for reg in _base_registers():
        registers.append(reg)
        registers.append(reg._replace(name=f"{reg.name}NoTimestamp", timestamped=False))
    return registers


BENCHMARK_REGISTERS: list[BenchmarkedRegister] = _build()
