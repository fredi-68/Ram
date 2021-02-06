class CommandException(Exception):

    def __init__(self, msg: str, mention_user=False):

        self.mention_user = mention_user

class CommandCallFailedException(CommandException):

    """
    Raised when an error occurs within a commands call() method.
    """

    pass

class CommandNotFoundException(CommandException):

    """
    Raised when a requested command does not exist.
    """

    pass

class PermissionDeniedException(CommandException):

    """
    Raised when the caller is lacking sufficient permission to use a command.
    """

    pass

class ArgumentException(Exception):

    """
    Raised by argument parsers if an error occurs during argument parsing.
    """

    pass

class CommandCallAbortedException(CommandException):

    """
    Raised by the parser if parsing was aborted for some reason.
    This exception should always be silenced.
    """

    pass