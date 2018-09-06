#Discord ProtOS Bot
#
#Author: fredi_68
#
#Stuff for ANSI control message handling

import logging
import sys
import platform

FORMATTING_AVAILABLE = True

_ver = list(map(int, platform.python_version_tuple())) #get python version tuple as int list
HAS_UTF8 = ((_ver[0] == 3 and _ver[1] > 5 ) or _ver[0] > 3) #Python version 3.6 introduces console UTF-8 support, enable if possible

#Windows has special needs
if sys.platform == "nt":

    #ANSI escape sequences are somewhat broken in Windows, although the Threshold 2 update was supposed to fix them (except it didn't).
    #Because no one actually understands which Windows versions support ANSI escape sequences and which don't, we'll just deactivate them
    #unless the system is running version 10.10586 or higher. This will most likely break on Win 10 systems with broken ANSI consoles.
    FORMATTING_AVAILABLE = False 
    _win_ver = sys.getwindowsversion()
    if _win_ver.major > 10 or (_win_ver.major == 10 and _win_ver.build >= 10586):

        FORMATTING_AVAILABLE = True #Activate new Win 10 console ANSI handling

COLORS = [ #ANSI color code mapping
    [0,0,0,"30;47"],
    [128,0,0,"31;47"],
    [0,128,0,"32;47"],
    [128,128,0,"33;47"],
    [0,0,128,"34;47"],
    [128,0,128,"35;47"],
    [0,128,128,"36;47"],
    [192,192,192,"37"],

    [128,128,128,"90"],
    [255,0,0,"91"],
    [0,255,0,"92"],
    [255,255,0,"93"],
    [0,0,255,"94;47"],
    [255,0,255,"95"],
    [0,255,255,"96"],
    [255,255,255,"97"]
    ]

COLOR_RESET = "\033[39;49m" #ANSI control message to reset color

def printSeparator(length=40):

    """
    Prints a separator to standart output.
    Optional length parameter defines how many characters the separator will consist of.
    Comes with an extra newline for increased readability.
    Example:
    printSeparator(40) => "----------------------------------------"
    """

    logging.info(formatText("-" * length + "\n", True))

def translateString(s):

    """
    Helper Method.
    Converts the string s to ASCII using backslashreplace if UTF-8 console mode is not supported.
    """

    if HAS_UTF8:
        return s

    return str(s.encode(), encoding = "ASCII", errors="backslashreplace")

def colorText(s, c):

    """
    Set the color of string s to the CLOSEST MATCH to color c.
    c is expected to be a list like with 3 integers as its items.
    Example: colorText("Hello World", [255,0,0])
    This function will automatically append a reset sequence after the text. Manually resetting the color is not necessary.
    """

    if not FORMATTING_AVAILABLE:
        return s

    HEAD = "\033["
    TAIL = "m"

    color = "39;49"
    lastDifference = 800

    for i in COLORS:
        diff = abs(i[0] - c[0]) + abs(i[1] - c[1]) + abs(i[2] - c[2]) #calculates difference to stock color
        if diff < lastDifference:
            lastDifference = diff #chooses closest match
            color = i[3]

    return HEAD+color+TAIL+s+COLOR_RESET #color code + string + reset code

def formatText(s, bold=False, underlined=False, negative=False):

    """
    Format the string s to be displayed as bold, underlined, negative or any combination of these.
    This function will automatically append a reset sequence after the text. Manually resetting the formatting is not necessary.
    """

    if not FORMATTING_AVAILABLE:
        return s

    head = ""
    if bold: head += "\033[1m"
    if underlined: head += "\033[4m"
    if negative: head += "\033[7m"

    return head + s + "\033[0m"
