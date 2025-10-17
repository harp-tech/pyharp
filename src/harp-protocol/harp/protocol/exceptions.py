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


class HarpTimeoutError(HarpException):
    """Raised when no reply is received within the configured timeout."""

    def __init__(self, timeout: float):
        """
        Creates a new HarpTimeoutError with the given timeout.

        Parameters
        ----------
        timeout: float
            Number of seconds waited before the timeout occurred.
        """
        super().__init__(f"No reply received within {timeout} seconds.")
        self.timeout = timeout
