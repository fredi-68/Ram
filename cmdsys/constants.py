"""
Backwards compatibility
"""

from .enums import CmdTypes

#Standard python types
CMD_TYPE_INT = CmdTypes.INT
CMD_TYPE_STR = CmdTypes.STR
CMD_TYPE_BOOL = CmdTypes.BOOL

#Discord.py specific types
CMD_TYPE_MESSAGE = CmdTypes.MESSAGE #WARNING: Must be in same channel as command message
CMD_TYPE_USER = CmdTypes.USER #Currently aliased to CMD_TYPE_MEMBER
CMD_TYPE_MEMBER = CmdTypes.MEMBER
CMD_TYPE_SERVER = CmdTypes.SERVER
CMD_TYPE_CHANNEL = CmdTypes.CHANNEL