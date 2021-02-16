from enum import Enum, auto

class OnDelete(Enum):

    CASCADE = auto()
    SET_NULL = auto()

class OnConflict(Enum):

    ROLLBACK = auto()
    NOTHING = auto()