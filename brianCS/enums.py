from enum import Enum

class Timeout(Enum):

    """
    Enum specifying the different timeout curves applied to messages in the buffer.
    """

    LINEAR = 0
    EXPONENTIAL = 1
    LOGARITHMIC = 2

class Dropout(Enum):

    """
    Enum specifying the different dropout algorithms for decreasing memory.
    """

    LEAST_USED = 0
    LEAST_FREQUENTLY = 1
    LEAST_RECENTLY_USED = 2
    RANDOM = 3
    RANDOM_WEIGHTED = 4
    ALL = 5
    NONE = 6

class DropoutCurve(Enum):

    """
    Specifies the dropout curve to apply when performing edge cleanup.
    """

    DECREMENT = 0
    HALF = 1
    LOG2 = 2
    LOG10 = 3
    SQUARE_ROOT = 4

class TokenTypes(Enum):

    START = 0
    END = 1
    WORD = 2
    SEPARATOR = 3
    LINK = 4

class Tags(Enum):

    NOUN = 0
    VERB = 1
    ADJECTIVE = 2
    ADVERB = 3
    PRONOUN = 4