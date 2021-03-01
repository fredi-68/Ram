"""
This package attempts to add voice receive functionality to discord.py
by hacking into the voice_client/voice ws.
"""

from .constants import *
from .opus import HAS_OPUS
from .listener import ConnectionListener
from .enums import *
from .sinks import *
from .speech import *

HAS_VOICE_REQ = True
try:
    import nacl
except ImportError as e:
    print("[Voicecom] CRITICAL ERROR: Unable to import nacl package, voice receive will not be available.")
    HAS_VOICE_REQ = False

if not HAS_OPUS:
    print("[Voicecom] CRITICAL ERROR: Opus is not initialized, voice receive will not be available.")
    HAS_VOICE_REQ = False