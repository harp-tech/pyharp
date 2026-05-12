"""Example: construct and parse every core Harp register payload.

Run with:
    uv run python scripts/core_registers_example.py
"""

from pathlib import Path

import numpy as np

from harp.device._registers import (
    # Enums / flags
    EnableFlag,
    OperationMode,
    # Payload classes
    ClockConfigPayload,
    DeviceNamePayload,
    OperationControlPayload,
    ResetDevicePayload,
    # Registers
    AssemblyVersion,
    ClockConfig,
    CoreVersionH,
    CoreVersionL,
    DeviceName,
    FirmwareVersionH,
    FirmwareVersionL,
    Heartbeat,
    HwVersionH,
    HwVersionL,
    OperationControl,
    ResetDevice,
    SerialNumber,
    TimestampMicro,
    TimestampOffset,
    TimestampSecond,
    WhoAmI,
)

from harp.protocol._message import HarpMessage

examples = [
    (WhoAmI, np.uint16(1216)),
    (TimestampSecond, np.uint32(3600)),
    (TimestampMicro, np.uint16(500)),
    (
        OperationControl,
        OperationControlPayload(
            operation_mode=OperationMode.Active,
            dump_registers=True,
            visual_indicators=EnableFlag.Enabled,
            operation_led=EnableFlag.Enabled,
            heartbeat=EnableFlag.Enabled,
        ),
    ),
    (ResetDevice, ResetDevicePayload(restore_default=True, restore_name=True)),
    (DeviceName, DeviceNamePayload("my-harp-device")),
    (ClockConfig, ClockConfigPayload(clock_repeater=True, clock_unlock=True)),
    (Heartbeat, np.uint16(1)),
    (HwVersionH, np.uint8(2)),
    (HwVersionL, np.uint8(0)),
    (AssemblyVersion, np.uint8(3)),
    (CoreVersionH, np.uint8(1)),
    (CoreVersionL, np.uint8(4)),
    (FirmwareVersionH, np.uint8(2)),
    (FirmwareVersionL, np.uint8(1)),
    (SerialNumber, np.uint16(42)),
    (TimestampOffset, np.uint8(0)),
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
    operation_mode=OperationMode.Active,
    heartbeat=EnableFlag.Enabled,
    visual_indicators=EnableFlag.Enabled,
)
print(f"  operation_mode    : {ctrl.operation_mode}")  # OperationMode.Active
print(f"  heartbeat         : {ctrl.heartbeat}")  # EnableFlag.Enabled
print(f"  dump_registers    : {ctrl.dump_registers}")  # False
print(f"  visual_indicators : {ctrl.visual_indicators}")  # EnableFlag.Enabled

# ---------------------------------------------------------------------------
# Bulk read from a .bin file (zero-copy, vectorised)
# ---------------------------------------------------------------------------
BIN_FILE = Path(__file__).parent.parent / "notes/Behavior.harp/Behavior_10.bin"
print(f"\n=== Bulk read from {BIN_FILE.name} ===")
_data, timestamps, msg_type, payload = OperationControl.parse_bulk(BIN_FILE.read_bytes())
print(f"  {len(timestamps)} frame(s) read")
print(f"  timestamps (s) : {timestamps}")
print(f"  operation_mode : {payload.operation_mode}")
print(f"  heartbeat      : {payload.heartbeat}")

print("\n  DataFrame:")
df = payload.to_dataframe()
df.insert(0, "timestamp", timestamps)
print(df.to_string(index=False))
