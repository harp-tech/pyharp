import pytest

from pyharp.protocol import CommonRegisters, MessageType, PayloadType
from pyharp.protocol.messages import (
    HarpMessage,
    ReadHarpMessage,
    ReplyHarpMessage,
    WriteHarpMessage,
)

DEFAULT_ADDRESS = 42


def test_create_write_float():
    """Test creating a write message with float value."""
    value = 3.14159
    message = WriteHarpMessage(PayloadType.Float, 42, value)

    assert message.message_type == MessageType.WRITE
    assert abs(message.payload - value) < 0.0001  # Float comparison
    assert len(message.frame) == 10  # 5 header bytes + 4 float bytes + 1 checksum


def test_create_write_list():
    """Test creating a write message with list values."""
    values = [10, 20, 30]
    message = WriteHarpMessage(PayloadType.U8, 42, values)

    # The frame should have length: 1 (type) + 1 (length) + 1 (address) + 1 (port) + 1 (payload_type) + 3 (values) + 1 (checksum)
    assert len(message.frame) == 9

    # Extract the payload portion from the frame
    payload_bytes = message.frame[5:8]
    # Verify each value in the payload bytes
    assert list(payload_bytes) == values


def test_create_error_cases():
    """Test error cases in HarpMessage.create()."""
    # Test invalid message type
    with pytest.raises(Exception) as excinfo:
        HarpMessage.create(MessageType.EVENT, 42, PayloadType.U8, 10)
    assert "valid message types" in str(excinfo.value)

    # Test WRITE with None value
    with pytest.raises(Exception) as excinfo:
        HarpMessage.create(MessageType.WRITE, 42, PayloadType.U8, None)
    assert "value cannot be None" in str(excinfo.value)


def test_reply_is_error():
    """Test ReplyHarpMessage.is_error property."""
    # Create a READ_ERROR message
    frame = bytearray(
        [
            MessageType.READ_ERROR,
            5,
            42,
            255,
            PayloadType.U8,
            0,
            0,
            0,
            0,  # timestamp seconds
            0,
            0,  # timestamp micros
            123,  # payload
            0,
        ]
    )  # checksum placeholder

    # Fix checksum
    checksum = sum(frame[:-1]) & 255
    frame[-1] = checksum

    reply = ReplyHarpMessage(frame)
    assert reply.is_error

    # Create a normal READ message
    frame = bytearray(
        [
            MessageType.READ,
            5,
            42,
            255,
            PayloadType.U8,
            0,
            0,
            0,
            0,  # timestamp seconds
            0,
            0,  # timestamp micros
            123,  # payload
            0,
        ]
    )  # checksum placeholder

    # Fix checksum
    checksum = sum(frame[:-1]) & 255
    frame[-1] = checksum

    reply = ReplyHarpMessage(frame)
    assert not reply.is_error


def test_create_read_U8() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.U8, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 47  # 1 + 4 + 42 + 255 + 1 - 256


def test_create_read_S8() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.S8, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 175  # 1 + 4 + 42 + 255 + 129 - 256


def test_create_read_U16() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.U16, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 48  # 1 + 4 + 42 + 255 + 2 - 256


def test_create_read_S16() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.S16, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 176  # 1 + 4 + 42 + 255 + 130 - 256


def test_create_read_U32() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.U32, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 50  # 1 + 4 + 42 + 255 + 4 - 256


def test_create_read_S32() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.S32, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 178  # 1 + 4 + 42 + 255 + 130 - 256


def test_create_read_U64() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.U64, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 54  # 1 + 4 + 42 + 255 + 2 - 256


def test_create_read_S64() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.S64, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 182  # 1 + 4 + 42 + 255 + 130 - 256


def test_create_read_float() -> None:
    message = ReadHarpMessage(payload_type=PayloadType.Float, address=DEFAULT_ADDRESS)

    assert message.message_type == MessageType.READ
    assert message.checksum == 114  # 1 + 4 + 42 + 255 + 4 - 256


def test_create_write_U8() -> None:
    value: int = 23
    message = WriteHarpMessage(PayloadType.U8, DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.WRITE
    assert message.payload == value
    assert message.checksum == 72  # 2 + 4 + 42 + 255 + 1 + 23 = 328 → 328 % 256 = 73


def test_create_write_S8() -> None:
    value: int = -3  # corresponds to signed int 253 (0xFD)
    message = WriteHarpMessage(PayloadType.S8, DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.WRITE
    assert message.payload == value
    assert message.checksum == 174  # (2 + 5 + 42 + 255 + 129 + 253) & 255


def test_create_write_U16() -> None:
    value: int = 1024  # 4 0 (2 x bytes)
    message = WriteHarpMessage(PayloadType.U16, DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.WRITE
    assert message.length == 6
    assert message.payload == value
    assert message.checksum == 55  # (2 + 6 + 42 + 255 + 2 + 4 + 0) & 255


def test_create_write_S16() -> None:
    value: int = -4837  # 27 237 (2 x bytes), corresponds to signed int 7149
    message = WriteHarpMessage(PayloadType.S16, DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.WRITE
    assert message.length == 6
    assert message.payload == value
    assert message.checksum == 187  # (2 + 6 + 42 + 255 + 130 + 27 + 237) & 255


def test_create_write_U8_array() -> None:
    values: list[int] = [1, 2, 3, 4, 5]
    message = WriteHarpMessage(PayloadType.U8, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert message.length == 4 + len(
        values
    )  # 7 header bytes + len(values) payload bytes
    assert message.payload == values
    assert message.checksum == 68  # (2 + (4 + 5) + 42 + 255 + 1 + 5) & 255


def test_create_write_S8_array() -> None:
    values: list[int] = [-1, -2, -3, -4, -5]
    message = WriteHarpMessage(PayloadType.S8, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert message.length == 4 + len(
        values
    )  # 7 header bytes + len(values) payload bytes
    assert message.payload == values
    assert message.checksum == 166  # (2 + (4 + 5) + 42 + 255 + 129 + 5) & 255


def test_create_write_U16_array() -> None:
    values: list[int] = [1, 2, 3, 4, 5]
    message = WriteHarpMessage(PayloadType.U16, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert (
        message.length == 4 + len(values) * 2
    )  # 7 header bytes + len(values) * 2 payload bytes
    assert message.payload == values
    assert message.checksum == 74  # (2 + (4 + 5 * 2) + 42 + 255 + 2 + 5) & 255


def test_create_write_S16_array() -> None:
    values: list[int] = [-1, -2, -3, -4, -5]
    message = WriteHarpMessage(PayloadType.S16, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert (
        message.length == 4 + len(values) * 2
    )  # 7 header bytes + len(values) * 2 payload bytes
    assert message.payload == values
    assert message.checksum == 167  # (2 + (4 + 5) + 42 + 255 + 129 + 5) & 255


def test_create_write_U32_array() -> None:
    values: list[int] = [1, 2, 3, 4, 5]
    message = WriteHarpMessage(PayloadType.U32, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert (
        message.length == 4 + len(values) * 4
    )  # 7 header bytes + len(values) * 4 payload bytes
    assert message.payload == values
    assert message.checksum == 86  # (2 + (4 + 5 * 4) + 42 + 255 + 4 + 5) & 255


def test_create_write_S32_array() -> None:
    values: list[int] = [-1, -2, -3, -4, -5]
    message = WriteHarpMessage(PayloadType.S32, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert (
        message.length == 4 + len(values) * 4
    )  # 7 header bytes + len(values) * 4 payload bytes
    assert message.payload == values
    assert message.checksum == 169  # (2 + (4 + 5 * 4) + 42 + 255 + 130 + 5) & 255


def test_create_write_U64_array() -> None:
    values: list[int] = [1, 2, 3, 4, 5]
    message = WriteHarpMessage(PayloadType.U64, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert (
        message.length == 4 + len(values) * 8
    )  # 7 header bytes + len(values) * 8 payload bytes
    assert message.payload == values
    assert message.checksum == 110  # (2 + (4 + 5 * 8) + 42 + 255 + 2 + 5) & 255


def test_create_write_S64_array() -> None:
    values: list[int] = [-1, -2, -3, -4, -5]
    message = WriteHarpMessage(PayloadType.S64, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    assert (
        message.length == 4 + len(values) * 8
    )  # 7 header bytes + len(values) * 8 payload bytes
    assert message.payload == values
    assert message.checksum == 173  # (2 + (4 + 5 * 8) + 42 + 255 + 130 + 5) & 255


def test_create_write_float_array() -> None:
    """Test creating a write message with float array values."""
    values = [1.1, 2.2, 3.3]
    message = WriteHarpMessage(PayloadType.Float, DEFAULT_ADDRESS, values)

    assert message.message_type == MessageType.WRITE
    expected_checksum = 193  # (2 + 4 + 42 + 255 + 1 + 3 * 4) & 255
    assert len(message.payload) == len(values)
    for actual, expected in zip(message.payload, values):
        assert abs(actual - expected) < 0.0001  # Float comparison with error margin
    assert message.checksum == expected_checksum


def test_read_who_am_i() -> None:
    message = ReadHarpMessage(
        payload_type=PayloadType.U16, address=CommonRegisters.WHO_AM_I
    )

    assert str(message.frame) == str(bytearray(b"\x01\x04\x00\xff\x02\x06"))


def test_create_write_U32() -> None:
    """Test creating a write message with S32 value."""
    value: int = 2147483000  # Large number
    message = WriteHarpMessage(PayloadType.U32, DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.WRITE
    assert message.length == 8
    assert message.payload == value
    assert len(message.frame) == 10  # length + checksum byte
    # Calculate checksum as in other tests
    expected_checksum = 42  # (2 + 8 + 42 + 255 + 4 + 0 + 0 + 0 + 0) & 255
    assert message.checksum == expected_checksum


def test_create_write_S32() -> None:
    """Test creating a write message with S32 value."""
    value: int = -2147483000  # Large negative number
    message = WriteHarpMessage(PayloadType.S32, DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.WRITE
    assert message.length == 8
    assert message.payload == value
    assert len(message.frame) == 10  # length + checksum byte
    # Calculate checksum as in other tests
    expected_checksum = 193  # (2 + 8 + 42 + 255 + 130 + 0 + 0 + 0 + 0) & 255
    assert message.checksum == expected_checksum


def test_create_write_U64() -> None:
    """Test creating a write message with U64 value."""
    value: int = 9223372036854775807  # Large 64-bit value
    message = WriteHarpMessage(PayloadType.U64, DEFAULT_ADDRESS, value)

    assert message.message_type == MessageType.WRITE
    assert message.length == 12  # 5 header bytes + 8 payload bytes
    assert message.payload == value
    assert len(message.frame) == 14  # length + checksum byte
    # Calculate checksum for 64-bit value
    expected_checksum = 183  # (2 + 12 + 42 + 255 + 2 + 0 + 0 + 0 + 0) & 255
    assert message.checksum == expected_checksum


def test_create_write_S64() -> None:
    """Test creating a write message with S64 value."""
    value: int = -9223372036854775807
    message = WriteHarpMessage(PayloadType.S64, DEFAULT_ADDRESS, value)
    assert message.message_type == MessageType.WRITE
    assert message.length == 12
    assert message.payload == value
    assert len(message.frame) == 14  # length + checksum byte
    # Calculate checksum for 64-bit signed value
    expected_checksum = 64  # (2 + 12 + 42 + 255 + 130 + 0 + 0 + 0 + 0) & 255
    assert message.checksum == expected_checksum


def test_reply_message_str_repr() -> None:
    """Test string representation of Reply message."""
    # Create a simple reply message
    frame = bytearray(
        [
            MessageType.READ,
            5,
            42,
            255,
            PayloadType.U8,
            0,
            0,
            0,
            0,  # timestamp seconds
            0,
            0,  # timestamp micros
            123,  # payload
            0,
        ]
    )  # checksum placeholder

    # Fix checksum
    checksum = sum(frame[:-1]) & 255
    frame[-1] = checksum

    reply = ReplyHarpMessage(frame)
    str_repr = str(reply)
    repr_str = repr(reply)

    assert "Type: READ" in str_repr
    assert "Length: 5" in str_repr
    assert "Address: 42" in str_repr
    assert "Port: 255" in str_repr
    assert "Payload: " in str_repr
    assert "Raw Frame" in repr_str


def test_payload_as_string() -> None:
    """Test ReplyHarpMessage.payload_as_string()."""
    test_string = "Hello"
    encoded = test_string.encode("utf-8")

    frame = bytearray(
        [
            MessageType.READ,
            5 + len(encoded),
            42,
            255,
            PayloadType.U8,
            0,
            0,
            0,
            0,  # timestamp seconds
            0,
            0,
        ]
    )  # timestamp micros

    # Add string payload
    frame.extend(encoded)
    # Add checksum
    frame.append(0)  # placeholder

    # Fix checksum
    checksum = sum(frame[:-1]) & 255
    frame[-1] = checksum

    reply = ReplyHarpMessage(frame)
    assert reply.payload_as_string() == test_string


def test_harp_message_parse() -> None:
    """Test the static parse method of HarpMessage."""
    frame = bytearray(
        [
            MessageType.READ,
            11,
            42,
            255,
            PayloadType.TimestampedU8,
            0,
            0,
            0,
            0,  # timestamp seconds
            0,
            0,  # timestamp micros
            123,  # payload
            0,
        ]
    )  # checksum placeholder

    # Fix checksum
    checksum = sum(frame[:-1]) & 255
    frame[-1] = checksum

    message = HarpMessage.parse(frame)
    assert isinstance(message, ReplyHarpMessage)
    assert message.message_type == MessageType.READ
    assert message.address == 42
    assert message.payload == 123


def test_timestamp_handling() -> None:
    """Test timestamp handling in ReplyHarpMessage."""
    # Create a timestamped message
    frame = bytearray(
        [
            MessageType.READ,
            5,
            42,
            255,
            PayloadType.TimestampedU8,
            1,
            0,
            0,
            0,  # timestamp seconds = 1
            32,
            0,  # timestamp micros = 32 (= 1ms)
            123,  # payload
            0,
        ]
    )  # checksum placeholder

    # Fix checksum
    checksum = sum(frame[:-1]) & 255
    frame[-1] = checksum

    reply = ReplyHarpMessage(frame)
    assert reply.timestamp is not None
    assert reply.timestamp == 1 + 32 * 32e-6  # 1 second + 1 millisecond

    # Create a non-timestamped message
    frame = bytearray(
        [
            MessageType.READ,
            5,
            42,
            255,
            PayloadType.U8,
            1,
            0,
            0,
            0,  # timestamp seconds = 1
            32,
            0,  # timestamp micros = 32 (= 1ms)
            123,  # payload
            0,
        ]
    )  # checksum placeholder

    # Fix checksum
    checksum = sum(frame[:-1]) & 255
    frame[-1] = checksum

    reply = ReplyHarpMessage(frame)
    assert reply.timestamp is None


def test_calculate_checksum() -> None:
    """Test the calculate_checksum method."""
    message = HarpMessage()
    message._frame = bytearray([1, 2, 3, 4, 5])

    # Sum is 15, checksum is 15 (no overflow)
    assert message.calculate_checksum() == 15

    message._frame = bytearray([200, 100, 50, 20, 10])
    # Sum is 380, checksum is 380 % 256 = 124
    assert message.calculate_checksum() == 124
