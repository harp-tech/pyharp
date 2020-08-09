from pyharp.messages import HarpMessage
from pyharp.messages import MessageType
from pyharp.messages import CommonRegisters

DEFAULT_ADDRESS = 42


def test_create_read_U8() -> None:
    message = HarpMessage.ReadU8(DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 47  # 1 + 4 + 42 + 255 + 1 - 256
    print(message.frame)


def test_create_read_S8() -> None:
    message = HarpMessage.ReadS8(DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 175  # 1 + 4 + 42 + 255 + 129 - 256
    print(message.frame)


def test_create_read_U16() -> None:
    message = HarpMessage.ReadU16(DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 48  # 1 + 4 + 42 + 255 + 2 - 256
    print(message.frame)


def test_create_read_S16() -> None:
    message = HarpMessage.ReadS16(DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 176  # 1 + 4 + 42 + 255 + 130 - 256
    print(message.frame)


def test_create_write_U8() -> None:
    value: int = 23
    message = HarpMessage.WriteU8(DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.Write
    assert message.payload == value
    assert message.checksum == 72  # 2 + 5 + 42 + 255 + 1 + 23 - 256
    print(message.frame)


def test_create_write_S8() -> None:
    value: int = -3  # corresponds to signed int 253 (0xFD)
    message = HarpMessage.WriteS8(DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.Write
    assert message.payload == value
    assert message.checksum == 174  # (2 + 5 + 42 + 255 + 129 + 253) & 255
    print(message.frame)


def test_create_write_U16() -> None:
    value: int = 1024  # 4 0 (2 x bytes)
    message = HarpMessage.WriteU16(DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.Write
    assert message.length == 6
    assert message.payload == value
    assert message.checksum == 55  # (2 + 6 + 42 + 255 + 2 + 4 + 0) & 255
    print(message.frame)


def test_create_write_S16() -> None:
    value: int = -4837  # 27 237 (2 x bytes), corresponds to signed int 7149
    message = HarpMessage.WriteS16(DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.Write
    assert message.length == 6
    assert message.payload == value
    assert message.checksum == 187  # (2 + 6 + 42 + 255 + 130 + 27 + 237) & 255
    print(message.frame)


def test_read_who_am_i() -> None:
    message = HarpMessage.ReadU16(CommonRegisters.WHO_AM_I)

    assert str(message.frame) == str(bytearray(b"\x01\x04\x00\xff\x02\x06"))
