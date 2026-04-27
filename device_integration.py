import time

import numpy as np
from harp.device import (
    AssemblyVersion,
    ClockConfig,
    CoreVersionH,
    CoreVersionL,
    Device,
    FirmwareVersionH,
    FirmwareVersionL,
    Heartbeat,
    HwVersionH,
    HwVersionL,
    OperationControl,
    ResetDevice,
    SerialNumber,
    TimestampMicro,
    TimestampSecond,
    WhoAmI,
)

PORT = "COM3"
N_READS = 10_000

CORE_REGISTERS = [
    ("WhoAmI", WhoAmI),
    ("HwVersionH", HwVersionH),
    ("HwVersionL", HwVersionL),
    ("AssemblyVersion", AssemblyVersion),
    ("CoreVersionH", CoreVersionH),
    ("CoreVersionL", CoreVersionL),
    ("FirmwareVersionH", FirmwareVersionH),
    ("FirmwareVersionL", FirmwareVersionL),
    ("TimestampSecond", TimestampSecond),
    ("TimestampMicro", TimestampMicro),
    ("OperationControl", OperationControl),
    ("ResetDevice", ResetDevice),
    ("SerialNumber", SerialNumber),
    ("ClockConfig", ClockConfig),
    (
        "Heartbeat",
        Heartbeat,
    ),  # TODO This is erroring out in pico devices. May be something with the serial class
]


def read_core_registers(dev: Device) -> None:
    print("\n=== Core register snapshot ===")
    print(f"{'Register':<20} {'Address':>7}  {'Value'}")
    print("-" * 50)
    for name, reg in CORE_REGISTERS:
        msg = dev.read(reg)
        print(f"{name:<20} {reg.address}   {msg.parsed}")

    # TODO just noticed the alias properties inside complex structs payloads like OperationControlPayload
    # are returning [value] instead of value. Prob decorate them with something and keep the internal array representation
    # hidden internally?


def whoa_latency_benchmark(dev: Device, n: int = N_READS) -> None:
    print(f"\n=== WhoAmI round-trip benchmark  (n={n:,}) ===")
    print("Collecting timestamps …")

    t0 = time.perf_counter()
    timestamps = np.empty(n, dtype=np.float64)
    for i in range(n):
        msg = dev.read(WhoAmI)
        timestamps[i] = msg.timestamp
    elapsed = time.perf_counter() - t0

    ts = np.array(timestamps, dtype=np.float64)
    if len(ts) < 2:
        print("Not enough timestamped replies to compute statistics.")
        return

    # Latency proxy: delta between successive device timestamps
    deltas_ms = np.diff(ts) * 1e3  # seconds → milliseconds

    print(f"\n  Total wall time : {elapsed:.2f} s  ({elapsed / n * 1e3:.2f} ms/read)")
    print(f"  Replies with TS : {len(ts):,} / {n:,}")
    print(f"\n  Inter-reply delta (ms)  [n={len(deltas_ms):,}]")
    print(f"    min    : {deltas_ms.min():.3f}")
    print(f"    p1     : {np.percentile(deltas_ms, 1):.3f}")
    print(f"    mean   : {deltas_ms.mean():.3f}")
    print(f"    std    : {deltas_ms.std():.3f}")
    print(f"    p99    : {np.percentile(deltas_ms, 99):.3f}")
    print(f"    max    : {deltas_ms.max():.3f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with Device(PORT) as dev:
        read_core_registers(dev)
        whoa_latency_benchmark(dev)
