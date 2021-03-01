"""
ProtOS Discord Bot

author: fredi_68

Command subsystem
"""

from .abcs import Command
from .arguments import *
from ._globals import SUPERUSERS, environment
from .errors import *
from .parser import CommandParser
from .utils import cleanUp, cleanUpRegister, dialogConfirm, dialogReact
from .model_commands import AddModelCommand, DeleteModelCommand
from .loader import load_commands