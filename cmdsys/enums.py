from enum import Enum, auto

#Argument types
class CmdTypes(Enum):

    #Standard python types
    INT = auto()
    STR = auto()
    BOOL = auto()
    FLOAT = auto() #new type

    #Discord.py types
    MESSAGE = auto()
    USER = auto()
    MEMBER = auto()
    SERVER = auto()
    CHANNEL = auto()
    ROLE = auto() #new type
    EMOTE = auto() #TODO: Implement