"""Example: construct and parse every core Harp register payload.

Run with:
    uv run python core_registers_example.py
"""

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
    (WhoAmI,           np.uint16(1216)),
    (TimestampSecond,  np.uint32(3600)),
    (TimestampMicro,   np.uint16(500)),
    (OperationControl, OperationControlPayload(
        operation_mode=OperationMode.Active,
        dump_registers=True,
        visual_indicators=EnableFlag.Enabled,
        operation_led=EnableFlag.Enabled,
        heartbeat=EnableFlag.Enabled,
    )),
    (ResetDevice,      ResetDevicePayload(restore_default=True, restore_name=True)),
    (DeviceName,       DeviceNamePayload("my-harp-device")),
    (ClockConfig,      ClockConfigPayload(clock_repeater=True, clock_unlock=True)),
    (Heartbeat,        np.uint16(1)),
    (HwVersionH,       np.uint8(2)),
    (HwVersionL,       np.uint8(0)),
    (AssemblyVersion,  np.uint8(3)),
    (CoreVersionH,     np.uint8(1)),
    (CoreVersionL,     np.uint8(4)),
    (FirmwareVersionH, np.uint8(2)),
    (FirmwareVersionL, np.uint8(1)),
    (SerialNumber,     np.uint16(42)),
    (TimestampOffset,  np.uint8(0)),
]

for register, value in examples:
    frame = register.format(value)
    parsed = register.parse(HarpMessage.parse(frame))
    print(f"{register.__name__:20s} (addr {register.address:2d})  →  {parsed}")
