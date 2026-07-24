import pytest
from harp.protocol._message_type import MessageType, message_type_from_byte, message_type_to_byte


@pytest.mark.parametrize(
    "byte, expected_type, expected_error",
    [
        (0x01, MessageType.Read, False),
        (0x02, MessageType.Write, False),
        (0x03, MessageType.Event, False),
        (0x09, MessageType.Read, True),  # Read + error flag
        (0x0A, MessageType.Write, True),  # Write + error flag
        (0x0B, MessageType.Event, True),  # Event + error flag
    ],
)
def test_from_byte_valid(byte, expected_type, expected_error):
    msg_type, has_error = message_type_from_byte(byte)
    assert msg_type == expected_type
    assert has_error == expected_error


@pytest.mark.parametrize(
    "byte",
    [
        0x00,  # type bits = 0, invalid
        0x04,  # type bits = 0 (bit 2 set, reserved)
        0x10,  # reserved bit 4
        0x20,  # reserved bit 5
        0x40,  # reserved bit 6
        0x80,  # reserved bit 7
        0xFF,  # everything set
    ],
)
def test_from_byte_invalid(byte):
    with pytest.raises(ValueError):
        message_type_from_byte(byte)


def test_to_byte_no_error():
    assert message_type_to_byte(MessageType.Read) == 0x01
    assert message_type_to_byte(MessageType.Write) == 0x02
    assert message_type_to_byte(MessageType.Event) == 0x03


def test_to_byte_with_error():
    assert message_type_to_byte(MessageType.Read, has_error=True) == 0x09
    assert message_type_to_byte(MessageType.Write, has_error=True) == 0x0A


def test_roundtrip():
    for mt in MessageType:
        for err in (False, True):
            b = message_type_to_byte(mt, err)
            mt2, err2 = message_type_from_byte(b)
            assert mt2 == mt
            assert err2 == err
