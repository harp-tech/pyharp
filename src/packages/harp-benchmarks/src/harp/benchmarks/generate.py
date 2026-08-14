import argparse
from pathlib import Path

import numpy as np

from harp.benchmarks._registers import BENCHMARK_REGISTERS, DATA_DIR, BenchmarkedRegister

_SEED = 42


def corpus_path(reg: BenchmarkedRegister, data_dir: Path = DATA_DIR):
    """Path to ``reg``'s corpus file under ``data_dir``."""
    return data_dir / reg.filename


def _frames(reg: BenchmarkedRegister, entries: int) -> np.ndarray:
    """Build ``entries`` frames of ``reg`` with a random per-frame payload.

    Bytes are held to the ASCII range (0..127) so every field varies while staying
    valid for any ``StringConverter`` member and free of float NaN/inf, since the corpus is
    decoded through ``to_columns`` and ``parse_to_dataframe`` during the benchmark. Timestamps,
    when present, are a monotonic ramp. Returns the flat uint8 wire buffer.
    """
    dtype = reg.register.payload_class.payload_dtype
    rng = np.random.default_rng(_SEED + reg.address)
    records = rng.integers(0, 128, size=entries * dtype.itemsize, dtype=np.uint8).view(dtype)
    timestamps = np.arange(entries, dtype=np.float64) if reg.timestamped else None
    return reg.register.format_bulk(records, timestamps=timestamps)


def generate_one(
    reg: BenchmarkedRegister, entries: int, data_dir: Path = DATA_DIR
) -> tuple[str, int, int]:
    """Write ``entries`` frames for ``reg``. Returns (path, frame_size, file_size)."""
    buf = _frames(reg, entries)
    path = corpus_path(reg, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.tobytes())
    return str(path), len(buf) // entries, path.stat().st_size


def ensure_corpus(
    reg: BenchmarkedRegister, entries: int, *, force: bool = False, data_dir: Path = DATA_DIR
) -> tuple[object, bool]:
    """Generate ``reg``'s corpus unless a matching cached file already exists.

    The cache is honored only when the size of the existing file matches ``entries``
    exactly (stride * entries); a stale file (different entry count) is rebuilt.
    Returns (path, generated).
    """
    path = corpus_path(reg, data_dir)
    if path.exists() and not force:
        stride = len(_frames(reg, 1))
        if path.stat().st_size == stride * entries:
            return path, False
    generate_one(reg, entries, data_dir)
    return path, True


def _select(only):
    selected = BENCHMARK_REGISTERS
    if only:
        wanted = set(only)
        selected = [r for r in BENCHMARK_REGISTERS if r.name in wanted]
        missing = wanted - {r.name for r in selected}
        if missing:
            raise SystemExit(f"Unknown register name(s): {', '.join(sorted(missing))}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entries", type=int, default=1_000_000, help="frames per register (default: 1,000,000)"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="NAME",
        help="restrict generation to these register names (default: all)",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=DATA_DIR,
        help=f"directory to write corpus files into (default: {DATA_DIR})",
    )
    args = parser.parse_args()

    selected = _select(args.only)
    args.dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.entries:,} frames/register into {args.dir}\n")
    total_bytes = 0
    for reg in selected:
        _, frame_size, file_size = generate_one(reg, args.entries, args.dir)
        total_bytes += file_size
        print(
            f"  {reg.name:<24s} addr={reg.address:<4d} "
            f"frame={frame_size:>3d}B  ->  {reg.filename:<32s} "
            f"({file_size / 1024**2:8.1f} MiB)"
        )
    print(f"\nDone. {len(selected)} file(s), {total_bytes / 1024**2:,.1f} MiB total.")


if __name__ == "__main__":
    main()
