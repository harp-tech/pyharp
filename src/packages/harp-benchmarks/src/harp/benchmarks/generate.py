import argparse
import sys

from harp.benchmarks._registers import BENCHMARK_REGISTERS, DATA_DIR, BenchmarkedRegister

_TIMESTAMP = 42


def corpus_path(reg: BenchmarkedRegister):
    """Path to ``reg``'s corpus file under the artifacts data directory."""
    return DATA_DIR / reg.filename


def _frame_timestamp(reg: BenchmarkedRegister) -> int | None:
    return _TIMESTAMP if reg.timestamped else None


def generate_one(reg: BenchmarkedRegister, entries: int) -> tuple[str, int, int]:
    """Write ``entries`` frames for ``reg``. Returns (path, frame_size, file_size)."""
    frame = reg.register.format(reg.value, timestamp=_frame_timestamp(reg))
    path = corpus_path(reg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(frame * entries)
    return str(path), len(frame), path.stat().st_size


def ensure_corpus(
    reg: BenchmarkedRegister, entries: int, *, force: bool = False
) -> tuple[object, bool]:
    """Generate ``reg``'s corpus unless a matching cached file already exists.

    The cache is honored only when the existing file's size matches ``entries``
    exactly (frame_size * entries); a stale file (different entry count) is rebuilt.
    Returns (path, generated).
    """
    path = corpus_path(reg)
    if path.exists() and not force:
        frame_size = len(reg.register.format(reg.value, timestamp=_frame_timestamp(reg)))
        if path.stat().st_size == frame_size * entries:
            return path, False
    generate_one(reg, entries)
    return path, True


def _use_utf8_console() -> None:
    """Best-effort: make console output UTF-8 (docstrings use non-ASCII glyphs)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


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
    _use_utf8_console()
    args = parser.parse_args()

    selected = _select(args.only)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.entries:,} frames/register into {DATA_DIR}\n")
    total_bytes = 0
    for reg in selected:
        _, frame_size, file_size = generate_one(reg, args.entries)
        total_bytes += file_size
        print(
            f"  {reg.name:<24s} addr={reg.address:<4d} "
            f"frame={frame_size:>3d}B  ->  {reg.filename:<32s} "
            f"({file_size / 1024**2:8.1f} MiB)"
        )
    print(f"\nDone. {len(selected)} file(s), {total_bytes / 1024**2:,.1f} MiB total.")


if __name__ == "__main__":
    main()
