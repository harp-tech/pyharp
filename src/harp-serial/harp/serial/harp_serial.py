import logging
import queue
import threading
from functools import partial
from typing import Union

import serial
import serial.threaded
from harp.protocol.exceptions import HarpException
from harp.protocol.messages import HarpMessage, MessageType


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
            The queue to where the data received will be put
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
            The data received from the serial communication
        """
        self._buffer.extend(data)
        while True:
            if len(self._buffer) < 2:
                # not enough data to read the message type and length
                break

            # Read length (we can ignore the message type)
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
        The queue containing the Harp messages that are not of the type `MessageType.EVENT`
    event_q : queue.Queue
        The queue containing the Harp messages of `MessageType.EVENT`
    """

    msg_q: queue.Queue
    event_q: queue.Queue

    def __init__(self, serial_port: str, **kwargs):
        """
        Parameters
        ----------
        serial_port : str
            The serial port used to establish the connection with the Harp device. It must be denoted as `/dev/ttyUSBx` in Linux and `COMx` in Windows, where `x` is the number of the serial port
        """
        ser_kwargs = dict(kwargs)
        ser_kwargs.setdefault("exclusive", True)
        # Connect to the Harp device
        try:
            self._ser = serial.Serial(serial_port, **ser_kwargs)
        except serial.serialutil.SerialException:
            raise HarpException(
                f"Error connecting to device. Resource might be busy or without proper permissions: {serial_port}"
            )

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
        self._reader.connect()

        # Start the thread that parses and separates the events from the remaining messages
        self._parse_thread = threading.Thread(
            target=self.parse_harp_msgs_threaded_buffered,
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
