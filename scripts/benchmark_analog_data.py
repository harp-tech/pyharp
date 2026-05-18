"""Benchmark: pyharp read_frames vs harp-python read for AnalogData (reg 44).

AnalogData — address 44, S16 array of length 3, named fields:
  analog_input0, encoder, analog_input1

The benchmark compares two strategies for decoding ~3.8M frames (~65 MB) of
AnalogData from a Harp binary file into a pandas DataFrame with named columns:

  harp-python strategy:
    harp_io.read(file, columns=[...])  →  DataFrame directly

  pyharp strategy:
    AnalogData.read_frames(file)  →  (timestamps, payload)
    payload.to_dataframe()        →  DataFrame with named columns

Both are zero-copy for the payload bytes (strided np.ndarray views into the raw
file buffer).  The harp-python path builds the DataFrame in one shot; the pyharp
path splits parsing from presentation.

Run with:
    uv run python scripts/benchmark_analog_data.py
"""

import sys
import timeit
from pathlib import Path
from typing import ClassVar

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts._harp_io import read as harp_read  # vendored harp-python read()

from harp.protocol._payload import PayloadBase, _Field
from harp.protocol._payload_type import PayloadType
from harp.protocol._register import RegisterBase
from harp.protocol._payload_converters import Int16Converter


REPO_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# AnalogData register definition (hand-written; would come from codegen)
# ---------------------------------------------------------------------------

ANALOG_COLUMNS = ["analog_input0", "encoder", "analog_input1"]


class AnalogDataPayload(PayloadBase[np.void]):
    """Payload for AnalogData (register 44): three signed 16-bit channels."""

    analog_input0 = _Field(converter=Int16Converter())
    encoder = _Field(converter=Int16Converter())
    analog_input1 = _Field(converter=Int16Converter())


class AnalogData(RegisterBase[AnalogDataPayload]):
    address: ClassVar[int] = 44
    payload_type: ClassVar[PayloadType] = PayloadType.S16
    payload_class: ClassVar[type[AnalogDataPayload]] = AnalogDataPayload
    # length = None → structured dtype; read_frames will treat it as 1 element
    # of size 6 bytes, squeezing to shape (N,).


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BIN_FILE = REPO_ROOT / "notes" / "Behavior.harp" / "Behavior_44.bin"


def pyharp_read(path: Path, *, include_timestamp: bool = True):
    """pyharp path: parse_bulk → to_dataframe."""
    bytes_2_parse = path.read_bytes()
    _data, timestamps, msg_type, payload = AnalogData.parse_bulk(bytes_2_parse)
    df = payload.to_dataframe()
    if include_timestamp:
        df.insert(0, "timestamp", timestamps)
    return df


def pyharp_read_dataframe(path: Path, *, timestamp: bool = True):
    """pyharp one-call path: read_dataframe."""
    return AnalogData.read_dataframe(path.read_bytes(), timestamp=timestamp)


def harp_python_read(path: Path):
    """harp-python path: read() directly to DataFrame."""
    return harp_read(path, columns=ANALOG_COLUMNS)


# ---------------------------------------------------------------------------
# Sanity check: both paths must produce the same values
# ---------------------------------------------------------------------------


def sanity_check() -> None:
    df_pyharp = pyharp_read(BIN_FILE)
    df_harp = harp_python_read(BIN_FILE)

    assert len(df_pyharp) == len(df_harp), (
        f"row count mismatch: pyharp={len(df_pyharp)}, harp-python={len(df_harp)}"
    )
    for col in ANALOG_COLUMNS:
        np.testing.assert_array_equal(
            df_pyharp[col].to_numpy(),
            df_harp[col].to_numpy(),
            err_msg=f"column {col!r} differs",
        )
    print(f"  Sanity check passed — {len(df_pyharp):,} rows, columns match.")


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

N_REPEATS = 100
N_LOOPS = 1


def benchmark(label: str, fn, path: Path) -> np.ndarray:
    times = np.array(timeit.repeat(lambda: fn(path), repeat=N_REPEATS, number=N_LOOPS))
    print(
        f"  {label:<45s}  "
        f"min={times.min():.3f}s  "
        f"mean={times.mean():.3f}s  "
        f"max={times.max():.3f}s  "
        f"(n={N_REPEATS})"
    )
    return times


if __name__ == "__main__":
    if not BIN_FILE.exists():
        print(f"ERROR: {BIN_FILE} not found. Place the Behavior_44.bin file there.")
        sys.exit(1)

    file_mb = BIN_FILE.stat().st_size / 1024**2

    # Quick probe for frame count
    data = np.fromfile(BIN_FILE, dtype=np.uint8)
    stride = int(data[1]) + 2
    nrows = len(data) // stride
    del data  # free before benchmarks

    print("\n=== AnalogData benchmark ===")
    print(f"  File  : {BIN_FILE.name}  ({file_mb:.1f} MB)")
    print(f"  Frames: {nrows:,}  |  stride={stride} bytes\n")

    print("Sanity check:")
    sanity_check()

    print(f"\nBenchmark ({N_REPEATS} repeats, 1 call each):")
    t_harp = benchmark("harp-python  read()", harp_python_read, BIN_FILE)
    t_py_ts = benchmark("pyharp       read_frames()+to_dataframe()+ts", pyharp_read, BIN_FILE)
    t_py_no_ts = benchmark(
        "pyharp       read_frames()+to_dataframe() (no ts)",
        lambda p: pyharp_read(p, include_timestamp=False),
        BIN_FILE,
    )
    t_py_rd = benchmark(
        "pyharp       read_dataframe(timestamp=True)",
        pyharp_read_dataframe,
        BIN_FILE,
    )
    t_py_rd_no_ts = benchmark(
        "pyharp       read_dataframe(timestamp=False)",
        lambda p: pyharp_read_dataframe(p, timestamp=False),
        BIN_FILE,
    )

    print("")
    for label, t_py in [
        ("read_frames + to_dataframe + ts", t_py_ts),
        ("read_frames + to_dataframe (no ts)", t_py_no_ts),
        ("read_dataframe(timestamp=True)", t_py_rd),
        ("read_dataframe(timestamp=False)", t_py_rd_no_ts),
    ]:
        ratio_min = t_py.min() / t_harp.min()
        ratio_mean = t_py.mean() / t_harp.mean()
        direction = "slower" if ratio_mean > 1 else "faster"
        print(
            f"  {label:<40s} vs harp-python :"
            f"  min={ratio_min:.2f}x  mean={ratio_mean:.2f}x"
            f"  ({direction} by {abs(ratio_mean - 1) * 100:.0f}% on mean)"
        )

    # Show a sample of the result
    print("\nSample output (pyharp, first 3 rows):")
    df = pyharp_read(BIN_FILE)
    print(df.head(3).to_string(index=False))
