#Discord ProtOS Bot
#
#Author: fredi_68
#
#Command subsystem

import discord
import logging
import enum

#Argument types
class CmdTypes(enum.Enum):

    #Standard python types
    INT = enum.auto()
    STR = enum.auto()
    BOOL = enum.auto()
    FLOAT = enum.auto() #new type

    #Discord.py types
    MESSAGE = enum.auto()
    USER = enum.auto()
    MEMBER = enum.auto()
    SERVER = enum.auto()
    CHANNEL = enum.auto()
    ROLE = enum.auto() #new type

#THESE CONSTANTS HAVE BEEN DEPRECATED IN FAVOUR OF
#CmdTypes ENUM. THERE WILL BE NO EFFORT MADE TO
#KEEP THESE UP TO DATE WITH THE REST OF THE CODEBASE,
#THEY MERELY EXIST TO PROVIDE BACKWARDS COMPATABILITY

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

CLEANUP_FUNCTIONS = []

logger = logging.getLogger("Command")

def cleanUpRegister(func, *args, **kwargs):

    """
    Register a function to be called at application exit.
    This is guaranteed to be called BEFORE the discord connection is terminated, unless the bot crashed.
    func must be an awaitable object.
    """

    logger.debug("Cleanup function registered: "+str(func))
    CLEANUP_FUNCTIONS.append([func,args,kwargs])

async def cleanUp():

    """
    Run all cleanup functions and finish up the command handlers.
    """

    for i in CLEANUP_FUNCTIONS:
        try:
            logger.debug("Running cleanup function "+str(i[0]))
            await i[0](*i[1],**i[2])
        except:
            logger.exception("Clean up function "+str(i[0])+" could not be executed correctly!")

class Argument():

    def __init__(self, name, type=CMD_TYPE_INT, optional=False,default=None):

        """
        Creates a new argument descriptor with a name and an associated type.
        If the argument is optional, the default should be set to a value accepted by the specified type.
        """

        self.name = name
        self.type = type
        self.optional = bool(optional)
        self.default = default

class Command():

    def __init__(self):

        """
        Base class for all Commands.
        This class needs to be subclassed to implement actual functionality.

        Please refer to commands/COMMANDS.TXT for more information
        """

        self.logger = logging.getLogger("Uninitialized Command")

        #System internal information
        self.name = ""
        self.aliases = []
        self.desc = "A command."
        self.arguments = []
        self.permissions = discord.Permissions.none()

        #Command flags (can be set by user)
        self.ownerOnly = False
        self.allowChat = True
        self.allowConsole = True
        self.hidden = False
        self.allowDelimiters = True

        #Environment variables (cannot be set by user)
        self.responseHandle = None
        self.client = None
        self.msg = None
        self.config = None
        self.db = None
        self.audioManager = None

        self.setup() #parse command attributes of subclasses

        self.logger = logging.getLogger("Command "+self.name)

        #If we don't do this, a command may be never called without it being noticed at dev time
        names = [self.name]
        names.extend(self.aliases)
        
        for i in names:
            if " " in i or not i:
                raise ValueError("Command names and aliases may not include whitespaces and must not be empty.")

    def setup(self):

        """
        Setup method. Override this to customize command attributes.
        """

        pass

    async def call(self, **kwargs):

        """
        Command body. This method is called when the command is executed with all specified arguments as keyword arguments.
        """

        return

    async def respond(self, msg, notify=False, flush_chat=True):

        """
        Helper method for printing command output.
        """

        await self.responseHandle.reply(msg, notify, flush_chat) #does all the work for us

    async def embed(self, embed):

        """
        Helper method for printing command output.
        """

        await self.responseHandle.createEmbed(embed)

    async def log(self, msg, notify=False):

        """
        Helper method for logging to audit logs.
        """

        db = self.db.getServer(self.msg.server.id)
        dsList = db.enumerateDatasets("auditLogChannels")
        for i in dsList:
            dch = self.msg.server.get_channel(i.getValue("channelID"))
            await self.client.send_message(dch, msg)

    async def flush(self):

        """
        Helper method.
        Flushes the internal message buffer.
        """

        await self.responseHandle.flush()

    def playSound(self, sound, channel, sync=True):

        """
        Play a sound on the specified channel.
        sound should be an instance of a subclass of audio.Sound.
        If sync is True, the sound will be queued, otherwise it will play
        immediately.
        """

        self.audioManager.playSound(sound, channel, sync)

    def addArgument(self, argument):

        """
        Add an argument
        """

        self.arguments.append(argument)

    def getUsage(self):

        """
        Get a usage string for the command e.g.
        "Usage: +test <arg1> [arg2]" 
        """

        cmds = [self.name]
        cmds.extend(self.aliases)

        prefix = self.config.getElementText("bot.prefix","+")

        s = "Usage: "+prefix+(", "+prefix).join(cmds)+" "
        for i in self.arguments:
            if i.optional:
                s += "["+i.name+"] "
            else:
                s += "<"+i.name+"> "

        return s

    def getHelp(self):

        """
        Get documentation for the command
        """

        s = self.desc+"\n"

        #add some information regarding permissions
        if self.ownerOnly:
            s += "\nOnly the bot owner can use this command."
        if not (self.allowChat or self.allowConsole): #for those weird cases where a command disables itself
            s += "\nThis command is currently unavailable."
        elif not self.allowChat:
            s += "\nThis command is console only."
        elif not self.allowConsole:
            s += "\nThis command is chat only."

        s += "\n\n"+self.getUsage()+"\n"

        s += "\nArguments:\n" #Give more information about arguments
        for i in self.arguments:
            s += "  '"+i.name+"' ("
            if i.optional:
                s += "optional"
            else:
                s += "required"
            s += ") type '"+str(i.type)+"'\n"

        return s

    def _setVariables(self, client, cfg, responseHandle, db, audioManager):

        """
        Internal method.
        Sets the environment attributes
        """

        self.client = client
        self.config = cfg
        self.responseHandle = responseHandle
        self.msg = responseHandle.getMessage()
        self.db = db
        self.audioManager = audioManager