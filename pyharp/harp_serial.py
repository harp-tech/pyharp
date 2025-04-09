import logging
import queue
import threading
from functools import partial
from typing import Union

import serial
import serial.threaded

from pyharp.messages import HarpMessage, MessageType


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
        for byte in data:
            self._read_q.put(byte)
        return super().data_received(data)

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

    def __init__(self, serial_port: str, **kwargs):
        """
        Parameters
        ----------
        serial_port : str
            the serial port used to establish the connection with the Harp device. It must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port
        """
        # Connect to the Harp device
        self._ser = serial.Serial(serial_port, **kwargs)

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize the message queues
        self._read_q = queue.Queue()
        self.msg_q = queue.Queue()
        self.event_q = queue.Queue()

        # Start the thread with the `HarpSerialProtocol`
        self._reader = serial.threaded.ReaderThread(
            self._ser,
            partial(HarpSerialProtocol, self._read_q),
        )
        self._reader.start()
        transport, protocol = self._reader.connect()

        # Start the thread that parses and separates the events from the remaining messages
        self._parse_thread = threading.Thread(
            target=self.parse_harp_msgs_threaded,
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

    def parse_harp_msgs_threaded(self):
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
