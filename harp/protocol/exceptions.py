class HarpException(Exception):
    """Base class for all exceptions raised related with Harp."""

    pass


class HarpWriteException(HarpException):
    def __init__(self, register, message):
        super().__init__(f"Error writing to register {register}: {message}")
        self.register = register
        self.message = message


class HarpReadException(HarpException):
    def __init__(self, register, message):
        super().__init__(f"Error reading from register {register}: {message}")
        self.register = register
        self.message = message
