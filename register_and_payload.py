"""Example: working with registers and payloads.

Shows how to construct, encode, and parse both a simple scalar register
(WhoAmI) and a structured register (OperationControl) — for a single
sample and for 5 concatenated samples (e.g. from a bulk read).

No device connection is required; everything runs offline.
"""

import numpy as np

from harp.device._registers import OperationControl, OperationControlPayload, WhoAmI

# ── Single OperationControlPayload ───────────────────────────────────────────

print("=== Single OperationControlPayload ===")

p = OperationControlPayload(
    operation_mode=1,  # Active
    dump_registers=False,
    mute_replies=False,
    heartbeat=True,
)
print(p)
print(f"  operation_mode : {p.operation_mode[0]}")
print(f"  heartbeat      : {p.heartbeat[0]}")

# Build a Write frame for this payload
write_frame = OperationControl.format(p)
print(f"  write frame    : {write_frame}")

# Build a Read request frame (no payload needed)
read_frame = OperationControl.format()
print(f"  read frame     : {read_frame}")

# Round-trip: encode to bytes and parse back
raw = p.raw_payload.tobytes()
recovered = OperationControl.parse(raw)
print(f"  recovered      : {recovered}")

# ── 5 concatenated OperationControlPayloads ──────────────────────────────────

print("\n=== 5 concatenated OperationControlPayloads ===")

samples = [OperationControlPayload(operation_mode=i % 3, heartbeat=bool(i % 2)) for i in range(5)]
bulk_bytes = b"".join(s.raw_payload.tobytes() for s in samples)

bulk = OperationControl.parse_bulk(bulk_bytes)
print(f"  samples        : {len(bulk)}")
print(f"  operation_mode : {bulk.operation_mode}")
print(f"  heartbeat      : {bulk.heartbeat}")
print(bulk.to_dataframe())

# ── WhoAmI (plain scalar register) ───────────────────────────────────────────

print("\n=== WhoAmI (scalar register) ===")

read_frame = WhoAmI.format()
print(f"  read frame : {read_frame.hex()}")

# Simulate a raw response payload (device id = 1234)
raw_who_am_i = np.array([1234], dtype=np.uint16).tobytes()
who = WhoAmI.parse(raw_who_am_i)
print(f"  device id  : {who.value}")
