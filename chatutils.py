#Discord ProtOS Bot
#
#Author: fredi_68
#
#Chat convenience methods. These mainly deal with string analysis and formatting

import re
import shlex

#REGULAR EXPRESSIONS

re_user_mention = re.compile("<@?!?(\d+?)>") #searches in non-greedy mode for a number after an @ or ! in brackets
re_role_mention = re.compile("<@&(\d+?)>")
re_channel_mention = re.compile("<#(\d+?)>")
re_split_cmd = re.compile("""((?:".+?") ?|(?:[^ ]+) ?)""")

def checkForMention(msg, id):

    """
    Checks the string for a user mention with user ID <id> and returns the position if found.
    """

    result = re_user_mention.search(msg)
    #try to match ANY user mention
    if result and result.group(1) == id:
        return result.span(0) #return position of the mention found
    return (0, 0)

def getMention(msg):

    """
    Checks the string for a user mention and returns the user ID
    """

    result = re_user_mention.search(msg)
    return int(result.group(1)) if result else None

def getRoleMention(msg):

    """
    Checks the string for a role mention and returns the role ID
    """

    result = re_role_mention.search(msg)
    return int(result.group(1)) if result else None

def getChannelMention(msg):

    """
    Checks the string for a channel mention and returns the channel ID
    """

    result = re_channel_mention.search(msg)
    return int(result.group(1)) if result else None

def splitCommandString(cmd):

    """
    Split argument string and return commmand and arguments as a list of strings
    """

    return shlex.split(cmd)

    # res = re_split_cmd.split(cmd)
    # words = []
    # for i in res:
    #     if i:
    #         words.append(i.strip('" '))

    # return words

def checkForWords(words, s, ignoreCase=True):

    """
    Helper function.
    Returns true if all items in words are contained in string s.
    Optional ignoreCase parameter specifies if word checks should be case sensitive.
    """

    if (not (isinstance(words,list) or isinstance(words,tuple))) or not isinstance(s, str): #Type checking
        return False

    if ignoreCase:
        s = s.lower()

    for i in words:
        if ignoreCase:
            i = i.lower()
        if not i in s: #check if s contains i
            return False
    return True

def getRole(server, id):

    """
    Helper function
    Returns the role with the given ID in this server, or None if it doesn't exist.
    Apparently Discord.py doesn't have this.
    """

    for role in server.roles:
        if role.id == id:
            return role

#MARKDOWN HELPERS

MARKDOWN_ESCAPE="\\"
MARKDOWN_SPECIAL_CHARS = [
    "*",
    "_",
    "~",
    "`"
    ]

def mdItalic(text):

    """
    Markdown helper.
    Make text appear italic.
    """

    return "*"+text+"*"

def mdBold(text):

    """
    Markdown helper.
    Make text appear bold.
    """

    return "**"+text+"**"

def mdUnderlined(text):

    """
    Markdown helper.
    Make text appear underlined.
    """

    return "__"+text+"__"

def mdCrossed(text):

    """
    Markdown helper.
    Make text appear crossed out.
    """

    return "~~"+text+"~~"

def mdCode(text):

    """
    Markdown helper.
    Make text appear as a code box.
    """

    return "`"+text+"`"

def mdMultiCode(text, language=None):

    """
    Markdown helper.
    Make text appear as a multiline code box.
    """

    return "```"+("["+language+"] ") if language else ""+text+"```"

def mdEscape(text):

    """
    Markdown helper.
    Escapes the given text such that every character is (idealy) displayed as it was entered (prevent markdown formatting)
    """

    #We do this by examining the text and adding an escape sequence for every special character we encounter
    for char in MARKDOWN_SPECIAL_CHARS:
        text = text.replace(char, MARKDOWN_ESCAPE+char)
    return text