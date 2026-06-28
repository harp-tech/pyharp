"""Example: construct and parse every core Harp register payload.

Run with:
    uv run python scripts/core_registers_example.py
"""

from pathlib import Path

import numpy as np

from harp.device import (
    # Enums / flags
    ClockConfigurationFlags,
    EnableFlag,
    OperationMode,
    ResetFlags,
    # Payload classes
    OperationControlPayload,
    # Registers
    AssemblyVersion,
    ClockConfiguration,
    CoreVersionHigh,
    CoreVersionLow,
    DeviceName,
    FirmwareVersionHigh,
    FirmwareVersionLow,
    HardwareVersionHigh,
    HardwareVersionLow,
    OperationControl,
    ResetDevice,
    SerialNumber,
    TimestampMicroseconds,
    TimestampSeconds,
    WhoAmI,
)

from harp.data import to_dataframe
from harp.protocol import HarpMessage

examples = [
    (WhoAmI, np.uint16(1216)),
    (TimestampSeconds, np.uint32(3600)),
    (TimestampMicroseconds, np.uint16(500)),
    (
        OperationControl,
        OperationControlPayload(
            operation_mode=OperationMode.ACTIVE,
            dump_registers=True,
            visual_indicators=EnableFlag.ENABLED,
            operation_led=EnableFlag.ENABLED,
            heartbeat=EnableFlag.ENABLED,
        ),
    ),
    (ResetDevice, ResetFlags.RESTORE_DEFAULT | ResetFlags.RESTORE_NAME),
    (DeviceName, "my-harp-device"),
    (ClockConfiguration, ClockConfigurationFlags.CLOCK_REPEATER | ClockConfigurationFlags.CLOCK_UNLOCK),
    (HardwareVersionHigh, np.uint8(2)),
    (HardwareVersionLow, np.uint8(0)),
    (AssemblyVersion, np.uint8(3)),
    (CoreVersionHigh, np.uint8(1)),
    (CoreVersionLow, np.uint8(4)),
    (FirmwareVersionHigh, np.uint8(2)),
    (FirmwareVersionLow, np.uint8(1)),
    (SerialNumber, np.uint16(42)),
]

print("=== Live round-trip (format → parse) ===")
for register, value in examples:
    frame = register.format(value)
    parsed = register.parse(HarpMessage.parse(frame))
    print(f"{register.__name__:20s} (addr {register.address:2d})  →  {parsed}")

# ---------------------------------------------------------------------------
# Single-record bitfield access (scalar, no [0] indexing needed)
# ---------------------------------------------------------------------------
print("\n=== Bitfield scalar access ===")
ctrl = OperationControlPayload(
    operation_mode=OperationMode.ACTIVE,
    heartbeat=EnableFlag.ENABLED,
    visual_indicators=EnableFlag.ENABLED,
)
print(f"  operation_mode    : {ctrl.operation_mode}")  # OperationMode.ACTIVE
print(f"  heartbeat         : {ctrl.heartbeat}")  # EnableFlag.ENABLED
print(f"  dump_registers    : {ctrl.dump_registers}")  # False
print(f"  visual_indicators : {ctrl.visual_indicators}")  # EnableFlag.ENABLED

# ---------------------------------------------------------------------------
# Bulk read from a .bin file (zero-copy, vectorised)
# ---------------------------------------------------------------------------
BIN_FILE = Path(
    r"C:\git\bruno-f-cruz\analysis-harlow-learning-sets\data\841312_2026-06-15_19-38-50\behavior\Behavior.harp\Behavior_10.bin"
)
print(f"\n=== Bulk read from {BIN_FILE.name} ===")
_data, timestamps, msg_type, payload = OperationControl.parse_bulk(BIN_FILE.read_bytes())
print(f"  {len(timestamps)} frame(s) read")
print(f"  timestamps (s) : {timestamps}")
print(f"  operation_mode : {payload.operation_mode}")
print(f"  heartbeat      : {payload.heartbeat}")

print("\n  DataFrame:")
df = to_dataframe(payload)
df.insert(0, "timestamp", timestamps)
print(df.to_string(index=False))
