import logging
import queue
import threading
from functools import partial
from typing import Union

import serial
import serial.threaded

from pyharp.protocol.messages import HarpMessage, MessageType


class HarpSerialProtocolOld(serial.threaded.Protocol):
    # Old implementation (per-byte queue)
    def __init__(self, read_q: queue.Queue, *args, **kwargs):
        self._read_q = read_q
        super().__init__(*args, **kwargs)

    def data_received(self, data: bytes) -> None:
        for byte in data:
            self._read_q.put(byte)
        return super().data_received(data)


class HarpSerialProtocol(serial.threaded.Protocol):
    """
    The `HarpSerialProtocol` class deals with the data received from the serial communication.
    """

    _read_q: queue.Queue

    def __init__(self, read_q: queue.Queue, *args, **kwargs):
        """
        Parameters
        ----------
        read_q : queue.Queue
            the queue to where the data received will be put
        """
        self._read_q = read_q
        self._buffer = bytearray()
        super().__init__(*args, **kwargs)

    def connection_made(self, transport: serial.threaded.ReaderThread) -> None:
        """
        _TODO_

        Parameters
        ----------
        transport : serial.threaded.ReaderThread
            _TODO_
        """
        return super().connection_made(transport)

    def data_received(self, data: bytes) -> None:
        """
        Receives data from the serial commmunication.

        Parameters
        ----------
        data : bytes
            the data received from the serial communication
        """
        self._buffer.extend(data)
        while True:
            if len(self._buffer) < 2:
                # not enough data to read the message type and length
                break

            message_type = self._buffer[0]
            message_length = self._buffer[1]
            total_length = 2 + message_length
            if len(self._buffer) < total_length:
                break

            frame = self._buffer[:total_length]
            self._buffer = self._buffer[total_length:]
            self._read_q.put(frame)

    def connection_lost(self, exc: Union[BaseException, None]) -> None:
        """
        _TODO_

        Parameters
        ----------
        exc : exc: Union[BaseException, None]
            _TODO_
        """
        return super().connection_lost(exc)


class HarpSerial:
    """
    The `HarpSerial` deals with the received Harp messages and separates the events from the remaining messages.

    Attributes
    ----------
    msg_q : queue.Queue
        the queue containing the Harp messages that are not of the type `MessageType.EVENT`
    event_q : queue.Queue
        the queue containing the Harp messages of `MessageType.EVENT`
    """

    msg_q: queue.Queue
    event_q: queue.Queue

    def __init__(self, serial_port: str, use_buffered_protocol: bool = True, **kwargs):
        """
        Parameters
        ----------
        serial_port : str
            the serial port used to establish the connection with the Harp device. It must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port
        use_buffered_protocol : bool
            whether to use the buffered protocol for reading data
        """
        # Connect to the Harp device
        self._ser = serial.Serial(serial_port, **kwargs)

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize the message queues
        self._read_q = queue.Queue()
        self.msg_q = queue.Queue()
        self.event_q = queue.Queue()

        # Start the thread with the `HarpSerialProtocol`
        self.use_buffered_protocol = use_buffered_protocol
        protocol_cls = (
            HarpSerialProtocol if use_buffered_protocol else HarpSerialProtocolOld
        )

        self._reader = serial.threaded.ReaderThread(
            self._ser,
            partial(protocol_cls, self._read_q),
        )
        self._reader.start()
        self._reader.connect()

        # Choose parsing method based on protocol
        parse_target = (
            self.parse_harp_msgs_threaded_buffered
            if use_buffered_protocol
            else self.parse_harp_msgs_threaded_per_byte
        )

        # Start the thread that parses and separates the events from the remaining messages
        self._parse_thread = threading.Thread(
            target=parse_target,
            daemon=True,
        )
        self._parse_thread.start()

    def close(self):
        """
        Closes the serial port.
        """
        self._reader.close()

    def write(self, data):
        """
        Writes data to the Harp device.
        """
        self._reader.write(data)

    def parse_harp_msgs_threaded_buffered(self):
        """
        Parses the Harp messages and separates the events from the remaining messages.
        """
        while True:
            frame = self._read_q.get()
            try:
                # Parses the bytearray into a ReplyHarpMessage object
                msg = HarpMessage.parse(frame)
                if msg.message_type == MessageType.EVENT:
                    self.event_q.put(msg)
                else:
                    self.msg_q.put(msg)
            except Exception as e:
                self.log.error(f"Error parsing message: {e}")
                self.log.debug(f"Raw data: {frame}")

    def parse_harp_msgs_threaded_per_byte(self):
        """
        Parses the Harp messages and separates the events from the remaining messages.
        """
        while True:
            # Gets the Harp message bytes based on the length byte of the message
            message_type = self._read_q.get(1)
            message_length = self._read_q.get(1)
            message_content = bytes([self._read_q.get() for _ in range(message_length)])
            self.log.debug(f"reply (type): {message_type}")
            self.log.debug(f"reply (length): {message_length}")
            self.log.debug(f"reply (payload): {message_content}")

            # Reconstructs the message into a bytearray
            frame = bytearray()
            frame.append(message_type)
            frame.append(message_length)
            frame += message_content
            # Parses the bytearray into a ReplyHarpMessage object
            msg = HarpMessage.parse(frame)

            # Puts the parsed Harp message into the correct queue
            if msg.message_type == MessageType.EVENT:
                self.event_q.put(msg)
            else:
                self.msg_q.put(msg)
