from typing import ClassVar

import numpy as np

from harp.protocol import (
    HarpMessage,
    MessageType,
    StructPayload,
    Field,
    StringConverter,
    IdentityConverter,
    PayloadType,
    RegisterBase,
)

# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------

#   FileSettings0:
#     address: 54
#     type: U8
#     access: Write
#     length: 45
#     description: "Struct to configure Analog Output Channel 0
#       File Player settings: cycles (U32), duration_us (U32),
#       update_frequency_hz (U32), path (U8 array, 33 elements)"


class FileSettings0Payload(StructPayload[np.uint8]):
    cycles: np.uint32 = Field(converter=IdentityConverter(np.uint32), offset=0)
    duration_us: np.uint32 = Field(converter=IdentityConverter(np.uint32), offset=4)
    update_frequency_hz: np.uint32 = Field(converter=IdentityConverter(np.uint32), offset=8)
    path: str = Field(
        converter=StringConverter(33), default="220khzwaveform", offset=12
    )  # defaults work too


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


class FileSettings0(RegisterBase[FileSettings0Payload]):
    address: ClassVar[int] = 54
    payload_type = PayloadType.U8
    payload_class = FileSettings0Payload


# ---------------------------------------------------------------------------
# Round-trip demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Build payload
    payload = FileSettings0Payload(  # The stubs for the constructor must be auto generated, but this already works
        cycles=np.uint32(
            3
        ),  # If you want to be correct, you should use the exact types for the fields, but the converters will handle it if you don't
        duration_us=250_000,  # however this still works
        update_frequency_hz=400,
    )
    print(f"Payload dtype  : {FileSettings0Payload.dtype}")
    print(f"Payload bytes  : {payload.raw_payload.tobytes().hex()}")
    print(f"Payload        : {payload}")
    print(f"  cycles              = {payload.cycles}")
    print(f"  duration_us         = {payload.duration_us}")
    print(f"  update_frequency_hz = {payload.update_frequency_hz}")
    print(f"  path                = {payload.path!r}")

    # 2. Encode → Harp wire frame
    frame = FileSettings0.format(payload, message_type=MessageType.Write)
    print(f"\nWire frame ({len(frame)} bytes): {frame.hex()}")

    # 3. Parse wire frame → HarpMessage
    msg = HarpMessage.parse(frame)
    print(f"\nHarpMessage    : {msg}")

    # 4. Parse payload from HarpMessage
    parsed = FileSettings0.parse(msg)
    print(f"\nParsed payload : {parsed}")
    print(f"  cycles              = {parsed.cycles}")
    print(f"  duration_us         = {parsed.duration_us}")
    print(f"  update_frequency_hz = {parsed.update_frequency_hz}")
    print(f"  path                = {parsed.path!r}")

    # 5. Assert round-trip integrity
    assert parsed.cycles == 3
    assert parsed.duration_us == 250_000
    assert parsed.update_frequency_hz == 400
    assert parsed.path == "220khzwaveform"
    print("\nRound-trip OK")
