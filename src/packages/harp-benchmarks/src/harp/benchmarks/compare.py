"""Render a Markdown comparison of two ``harp-benchmark --json`` result files.

Used by CI to post a base-vs-PR parsing-speed diff as a pull-request comment. The
output is pure Markdown; a hidden ``<!-- harp-bench:{label} -->`` marker lets the
workflow keep a single sticky comment per runner. This is a comparison only — the
command always exits 0 (merges are never gated on it).
"""

import argparse
import json
import sys
from pathlib import Path

# Keep in sync with harp.benchmarks.benchmark.METRIC_LABELS / BENCHMARK_SCHEMA_VERSION.
METRIC_LABELS: dict[str, str] = {
    "bulk_preread": "parse_bulk (pre-read)",
    "bulk_reread": "parse_bulk (re-read)",
    "cols": "to_columns (decode)",
    "df_preread": "parse_to_dataframe (pre-read)",
    "df_reread": "parse_to_dataframe (re-read)",
}
DEFAULT_THRESHOLD = 10.0  # percent; |Δ| in min-time beyond this is called out


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _index(payload: dict) -> dict[str, dict]:
    """Map register name -> its record (metrics, frames, ...)."""
    return {r["name"]: r for r in payload.get("registers", [])}


def _ms(seconds: float) -> float:
    return seconds * 1e3


def _pct(base: float, pr: float) -> float | None:
    """Percent change base->pr; positive means slower (a regression). None if base is 0."""
    if base == 0:
        return None
    return (pr - base) / base * 100.0


def _fmt_pct(p: float | None) -> str:
    return "—" if p is None else f"{p:+.1f}%"


def _flag(p: float | None, threshold: float) -> str:
    if p is None:
        return ""
    if p >= threshold:
        return " ⚠️"
    if p <= -threshold:
        return " ✅"
    return ""


def _environment_table(base_env: dict, pr_env: dict) -> tuple[list[str], list[str]]:
    """Return (markdown lines, warnings) for the base-vs-PR environment block."""
    keys = ["platform", "python", "numpy", "pandas", "entries", "runs"]
    lines = ["| Key | base | PR |", "| --- | --- | --- |"]
    warnings: list[str] = []
    for k in keys:
        b, p = base_env.get(k, "?"), pr_env.get(k, "?")
        same = b == p
        lines.append(f"| {k} | {b} | {p} |")
        # A different interpreter/numpy/pandas makes absolute timings incomparable.
        if not same and k in {"python", "numpy", "pandas", "platform"}:
            warnings.append(f"`{k}` differs (base `{b}` vs PR `{p}`)")
    return lines, warnings


def _collect_deltas(
    base_regs: dict[str, dict], pr_regs: dict[str, dict]
) -> list[tuple[str, str, float, float, float]]:
    """(register, metric, base_min_ms, pr_min_ms, delta_pct) for every shared register+metric."""
    rows: list[tuple[str, str, float, float, float]] = []
    for name in base_regs.keys() & pr_regs.keys():
        b_metrics = base_regs[name]["metrics"]
        p_metrics = pr_regs[name]["metrics"]
        for metric in METRIC_LABELS:
            if metric not in b_metrics or metric not in p_metrics:
                continue
            b_min, p_min = b_metrics[metric]["min"], p_metrics[metric]["min"]
            pct = _pct(b_min, p_min)
            if pct is None:
                continue
            rows.append((name, metric, _ms(b_min), _ms(p_min), pct))
    return rows


def _summary_section(
    deltas: list[tuple[str, str, float, float, float]], threshold: float
) -> list[str]:
    """Notable min-time movers, worst regressions first."""
    notable = sorted(
        (d for d in deltas if abs(d[4]) >= threshold), key=lambda d: d[4], reverse=True
    )
    lines = [f"### Summary (min-time changes ≥ ±{threshold:g}%)", ""]
    if not deltas:
        lines.append("_No overlapping registers to compare._")
        return lines
    if not notable:
        lines.append(f"No min-time changes beyond ±{threshold:g}%. 🎉")
        return lines
    lines.append("| Register | Metric | base (ms) | PR (ms) | Δ min |")
    lines.append("| --- | --- | ---: | ---: | ---: |")
    for name, metric, b_ms, p_ms, pct in notable:
        lines.append(
            f"| {name} | {METRIC_LABELS[metric]} | {b_ms:.3f} | {p_ms:.3f} "
            f"| {_fmt_pct(pct)}{_flag(pct, threshold)} |"
        )
    return lines


def _detail_tables(
    base_regs: dict[str, dict], pr_regs: dict[str, dict], threshold: float
) -> list[str]:
    """One collapsible table per measured operation: min/mean/max/std, base vs PR."""
    lines: list[str] = []
    names = sorted(base_regs.keys() & pr_regs.keys())
    for metric, label in METRIC_LABELS.items():
        lines.append(f"<details><summary>{label} — per register (ms)</summary>")
        lines.append("")
        lines.append(
            "| Register | mean base | mean PR | Δ mean | min base | min PR | Δ min "
            "| max base | max PR | std base | std PR |"
        )
        lines.append(
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
        )
        for name in names:
            b = base_regs[name]["metrics"].get(metric)
            p = pr_regs[name]["metrics"].get(metric)
            if b is None or p is None:
                continue
            d_mean = _pct(b["mean"], p["mean"])
            d_min = _pct(b["min"], p["min"])
            lines.append(
                f"| {name} "
                f"| {_ms(b['mean']):.3f} | {_ms(p['mean']):.3f} | {_fmt_pct(d_mean)} "
                f"| {_ms(b['min']):.3f} | {_ms(p['min']):.3f} | {_fmt_pct(d_min)}{_flag(d_min, threshold)} "
                f"| {_ms(b['max']):.3f} | {_ms(p['max']):.3f} "
                f"| {_ms(b['stdev']):.3f} | {_ms(p['stdev']):.3f} |"
            )
        lines.append("")
        lines.append("</details>")
        lines.append("")
    return lines


def render(base: dict, pr: dict, *, label: str, threshold: float) -> str:
    marker = f"<!-- harp-bench:{label} -->" if label else "<!-- harp-bench -->"
    title = f"## 🏁 Parsing benchmark — base vs PR{f' ({label})' if label else ''}"
    lines: list[str] = [marker, "", title, ""]

    env_lines, warnings = _environment_table(base.get("environment", {}), pr.get("environment", {}))
    if warnings:
        lines.append(
            "> ⚠️ Environment differs, so absolute timings are not directly comparable: "
            + "; ".join(warnings)
            + "."
        )
        lines.append("")
    lines.append("<details><summary>Environment</summary>")
    lines.append("")
    lines.extend(env_lines)
    lines.append("")
    lines.append("</details>")
    lines.append("")

    base_regs, pr_regs = _index(base), _index(pr)
    added = sorted(pr_regs.keys() - base_regs.keys())
    removed = sorted(base_regs.keys() - pr_regs.keys())
    if added:
        lines.append(f"> ➕ Only in PR: {', '.join(added)}")
        lines.append("")
    if removed:
        lines.append(f"> ➖ Only in base: {', '.join(removed)}")
        lines.append("")

    deltas = _collect_deltas(base_regs, pr_regs)
    lines.extend(_summary_section(deltas, threshold))
    lines.append("")
    lines.append(
        "_Δ is `(PR − base) / base`; positive = slower (regression). "
        "**min** is the headline (most stable on shared CI runners); mean/max/std shown for context._"
    )
    lines.append("")
    lines.extend(_detail_tables(base_regs, pr_regs, threshold))
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True, help="baseline results JSON")
    parser.add_argument("--pr", type=Path, required=True, help="PR results JSON")
    parser.add_argument(
        "--out", type=Path, default=None, help="write Markdown here (default: stdout)"
    )
    parser.add_argument(
        "--label", default="", help="runner label, e.g. the OS (sticky-comment key)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"|Δ min-time| %% to flag (default: {DEFAULT_THRESHOLD:g})",
    )
    args = parser.parse_args()

    md = render(_load(args.base), _load(args.pr), label=args.label, threshold=args.threshold)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"Comparison written to {args.out}")
    else:
        sys.stdout.write(md)


if __name__ == "__main__":
    main()
