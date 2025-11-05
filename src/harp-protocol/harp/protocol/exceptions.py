from typing import Optional

from harp.protocol.messages import HarpMessage


class HarpException(Exception):
    """Base class for all exceptions raised related with Harp."""

    def __init__(self, error_msg: str, message: Optional[HarpMessage] = None):
        """
        Creates a new HarpException with the given error message.

        Parameters
        ----------
        error_msg: str
            The error message describing the exception.
        message: Optional[HarpMessage]
            The Harp message that caused the exception, if applicable.
        """
        super().__init__(error_msg)
        self.message = message


class HarpWriteException(HarpException):
    """
    Exception raised when there is an error writing to a register in the Harp device.
    """

    def __init__(self, register_str: str, message: HarpMessage):
        """
        Creates a new HarpWriteException for the given register.

        Parameters
        ----------
        register_str: str
            The register string where the write error occurred.
        message: HarpMessage
            The Harp message that caused the write error.
        """
        super().__init__(f"Error writing to device on address {register_str}.", message)


class HarpReadException(HarpException):
    """
    Exception raised when there is an error reading from a register in the Harp device.
    """

    def __init__(self, register_str: str, message: HarpMessage):
        """
        Creates a new HarpReadException for the given register.

        Parameters
        ----------
        register_str: str
            The register string where the read error occurred.
        message: HarpMessage
            The Harp message that caused the read error.
        """
        super().__init__(f'Error reading from register "{register_str}".', message)


class HarpTimeoutException(HarpException):
    """Raised when no reply is received within the configured timeout."""

    def __init__(self, timeout: float, message: HarpMessage):
        """
        Creates a new HarpTimeoutException with the given timeout.

        Parameters
        ----------
        timeout: float
            The timeout duration in seconds.
        message: HarpMessage
            The Harp message that was sent when the timeout occurred.
        """
        error_msg = (
            f"No reply received within {timeout} seconds for message:\r\n{message}"
        )
        super().__init__(error_msg, message)
        self.timeout = timeout
