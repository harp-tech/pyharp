from typing import Optional

from harp.protocol.messages import HarpMessage


class HarpException(Exception):
    """Base class for all exceptions raised related with Harp."""

    pass


class HarpWriteException(HarpException):
    """
    Exception raised when there is an error writing to a register in the Harp device.
    """

    def __init__(self, register):
        super().__init__(f"Error writing to register {register}")
        self.register = register


class HarpReadException(HarpException):
    """
    Exception raised when there is an error reading from a register in the Harp device.
    """

    def __init__(self, register):
        super().__init__(f"Error reading from register {register}")
        self.register = register


class HarpTimeoutException(HarpException):
    """Raised when no reply is received within the configured timeout."""

    def __init__(self, timeout: float, message: Optional[HarpMessage] = None):
        """
        Creates a new HarpTimeoutException with the given timeout.

        Parameters
        ----------
        timeout: float
            The timeout duration in seconds.
        message: HarpMessage, optional
            The Harp message that was sent when the timeout occurred.
        """
        if message is None:
            error_msg = f"No reply received within {timeout} seconds."
        else:
            error_msg = (
                f"No reply received within {timeout} seconds for message:\r\n{message}"
            )

        super().__init__(error_msg)
        self.timeout = timeout
        self.message = message
