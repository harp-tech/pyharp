class HarpException(Exception):
    """Base class for all exceptions raised related with Harp."""

    pass


class HarpWriteException(HarpException):
    """
    Exception raised when there is an error writing to a register in the Harp device.
    """

    def __init__(self, register, message):
        super().__init__(f"Error writing to register {register}: {message}")
        self.register = register
        self.message = message


class HarpReadException(HarpException):
    """
    Exception raised when there is an error reading from a register in the Harp device.
    """

    def __init__(self, register, message):
        super().__init__(f"Error reading from register {register}: {message}")
        self.register = register
        self.message = message
