"""Pydantic object model of a Harp ``device.yml`` / ``registers`` schema.

TODO: hand-maintained for now. Auto-generating it from the upstream
``harp-tech/protocol`` JSON schema is deferred until that schema stabilises.
"""

from enum import Enum
from typing import Annotated, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel


class PayloadType(str, Enum):
    """Register payload element type. Values match the schema enum (the yml names)."""

    U8 = "U8"
    S8 = "S8"
    U16 = "U16"
    S16 = "S16"
    U32 = "U32"
    S32 = "S32"
    U64 = "U64"
    S64 = "S64"
    Float = "Float"


class Access(Enum):
    Read = "Read"
    Write = "Write"
    Event = "Event"


class Visibility(Enum):
    public = "public"
    private = "private"


class Converter(Enum):
    None_ = "None"
    Payload = "Payload"
    RawPayload = "RawPayload"


class MaskValueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int = Field(..., description="Specifies the numerical mask value.")
    description: Optional[str] = Field(None, description="Summary of the mask value function.")

    def __int__(self) -> int:
        return self.value


class MaskValue(RootModel[Union[int, MaskValueItem]]):
    root: Union[int, MaskValueItem]

    def __int__(self) -> int:
        return int(self.root)


class BitMask(BaseModel):
    description: Optional[str] = Field(None, description="Summary of the bit mask function.")
    bits: Dict[str, MaskValue]


class GroupMask(BaseModel):
    description: Optional[str] = Field(None, description="Summary of the group mask function.")
    values: Dict[str, MaskValue]


class MaskType(RootModel[str]):
    root: str


class InterfaceType(RootModel[str]):
    root: str


class MinValue(RootModel[float]):
    root: float


class MaxValue(RootModel[float]):
    root: float


class DefaultValue(RootModel[float]):
    root: float


class PayloadMember(BaseModel):
    mask: Optional[int] = Field(None, description="Mask used to read/write this member.")
    offset: Optional[int] = Field(None, description="Payload array offset of this member.")
    length: Optional[int] = Field(None, description="Number of base elements this member spans.")
    description: Optional[str] = Field(None, description="Summary of the payload member.")
    minValue: Optional[MinValue] = None
    maxValue: Optional[MaxValue] = None
    defaultValue: Optional[DefaultValue] = None
    maskType: Optional[MaskType] = None
    interfaceType: Optional[InterfaceType] = None
    converter: Optional[Converter] = None


class Register(BaseModel):
    address: Annotated[int, Field(le=255, description="Unique 8-bit register address.")]
    type: PayloadType
    length: Annotated[Optional[int], Field(ge=1, default=1, description="Payload length.")]
    access: Union[Access, List[Access]] = Field(..., description="Expected use of the register.")
    description: Optional[str] = Field(None, description="Summary of the register function.")
    minValue: Optional[MinValue] = None
    maxValue: Optional[MaxValue] = None
    defaultValue: Optional[DefaultValue] = None
    maskType: Optional[MaskType] = None
    visibility: Optional[Visibility] = Field(
        None, description="Exposed in the high-level interface."
    )
    volatile: Optional[bool] = Field(None, description="Value can be saved in non-volatile memory.")
    payloadSpec: Optional[Dict[str, PayloadMember]] = None
    interfaceType: Optional[InterfaceType] = None
    converter: Optional[Converter] = None


class Registers(BaseModel):
    """A bare register collection — a header-less ``device.yml`` fragment."""

    registers: Dict[str, Register] = Field(..., description="The device's registers.")
    bitMasks: Optional[Dict[str, BitMask]] = None
    groupMasks: Optional[Dict[str, GroupMask]] = None


class DeviceModel(Registers):
    """A device schema: a `Registers` collection plus (optional) device identity.

    Every identity field is optional, so a header-less fragment (just ``registers``
    / ``bitMasks`` / ``groupMasks``) is simply a ``DeviceModel`` with them all None
    — parsing never needs to branch on "fragment vs full document".
    """

    device: Optional[str] = Field(None, description="The name of the device.")
    whoAmI: Optional[int] = Field(None, description="Unique identifier for this device type.")
    firmwareVersion: Optional[str] = Field(
        None, description="Semantic version of the device firmware."
    )
    hardwareTargets: Optional[str] = Field(
        None, description="Semantic version of the device hardware."
    )
