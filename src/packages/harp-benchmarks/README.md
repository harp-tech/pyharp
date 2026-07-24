# harp-benchmarks

**Internal** parsing-speed benchmarks for the Harp register/payload API, run over every
register defined in [`register_models.py`](src/harp/benchmarks/register_models.py) (the
device.yml coverage model — also imported by the acceptance tests under `tests/`).

> This package is **not published to PyPI** (`classifiers = ["Private :: Do Not Upload"]`
> in its `pyproject.toml`). It is a workspace member consumed only in dev/internal builds
> via the repo-root `pyproject.toml` `dev` dependency-group. Its console scripts ship with
> this package, so they never leak into the published `harp` distribution.

## Layout

| Path | Purpose |
| --- | --- |
| `src/harp/benchmarks/register_models.py` | Reference models for every device.yml register (fixtures shared with the acceptance tests). |
| `src/harp/benchmarks/_registers.py` | Registry: each register + a representative sample value; artifact paths. |
| `src/harp/benchmarks/generate.py` | Writes `./benchmark/data/<Name>_<addr>.bin`; exposes `ensure_corpus` (cache-aware). |
| `src/harp/benchmarks/benchmark.py` | Ensures corpora exist, then times `parse_bulk`, `parse_to_dataframe`, `to_columns`; writes `./benchmark/report.md`. |

All generated artifacts (corpora + report) are written under **`./benchmark`** in the
current working directory — git-ignored and fully regenerable.

## Usage

Console scripts are declared in this package's `pyproject.toml`:

```bash
# One command: generate-if-needed (cache honored), then benchmark + write the report.
uv run harp-benchmark
uv run harp-benchmark --runs 20
uv run harp-benchmark --entries 100000 --force            # rebuild smaller corpora
uv run harp-benchmark --only Version ComplexConfiguration

# Generate corpora explicitly (optional — harp-benchmark does this for you).
uv run harp-benchmark-generate
uv run harp-benchmark-generate --entries 100000
```

Equivalent module invocations: `uv run python -m harp.benchmarks.benchmark` /
`uv run python -m harp.benchmarks.generate`.

## What is measured

- **`parse_bulk`** — the core zero-copy strided-view parse into a `Batch` payload.
  This is **lazy**: it builds strided views only and runs **no** converters.
- **`parse_to_dataframe`** — the full path to a pandas `DataFrame` (`copy=False`).
- **`to_columns`** (decode only) — `parse_bulk` views built once up front, then only
  `payload.to_columns()` timed. This is where each field's `converter.decode_batch`
  actually runs, with no file read and no pandas construction.

`parse_bulk` and `parse_to_dataframe` are each timed in two modes:

- **pre-read** — file read once up front; only deserialization is timed (isolates library speed).
- **re-read** — file re-read from disk on every run (real-world "load a dump" path, includes disk).

The report also decomposes `parse_to_dataframe ≈ parse_bulk + to_columns + pandas overhead`.
