import logging
import asyncio
import discord

from ._globals import environment
from core_models import AuditLogChannel

class Argument():

    def __init__(self, name: str, optional=False, default=None):

        self.name = name.lower()
        self.optional = optional
        self.default = default

    async def parse(self, client: "ProtosBot", argument: str, response_handle: "ResponseManager", command: "Command") -> object:

        raise NotImplementedError

class Command():

    def __init__(self):

        """
        Base class for all commands.
        This class needs to be subclassed to implement actual functionality.

        Please refer to commands/commands.TXT for more information
        """

        self.logger = logging.getLogger("Uninitialized Command")
        self._tasks = []
        self.loop = asyncio.get_event_loop()

        #System internal information
        self.name = ""
        self.aliases = []
        self.desc = "A command."
        self.arguments = []
        self.permissions = discord.Permissions.none()
        self.subcommands = []

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
        self.names = [self.name.lower()]
        self.names.extend(map(str.lower, self.aliases))
        
        for i in self.names:
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

    async def respond(self, msg: str, notify=False, flush_chat=True):

        """
        Helper method for printing command output.
        """

        await self.responseHandle.reply(msg, notify, flush_chat) #does all the work for us

    async def embed(self, embed: discord.Embed):

        """
        Helper method for printing command output.
        """

        await self.responseHandle.createEmbed(embed)

    async def log(self, msg: str, notify=False):

        """
        Helper method for logging to audit logs.
        """

        for i in environment.database.get_db_by_message(self.msg).query(AuditLogChannel):
            dch = await environment.client.fetch_channel(i.channel_id)
            await dch.send(msg)

    async def flush(self):

        """
        Helper method.
        Flushes the internal message buffer.
        """

        await self.responseHandle.flush()

    def playSound(self, sound: "audio.Sound", channel: discord.VoiceChannel, sync=True):

        """
        Play a sound on the specified channel.
        sound should be an instance of a subclass of audio.Sound.
        If sync is True, the sound will be queued, otherwise it will play
        immediately.
        """

        self.audioManager.playSound(sound, channel, sync)

    def getAuthorPermissions(self) -> discord.Permissions:

        """
        Return the discord.Permissions object associated with the author of
        the message that invoked this command.
        This can be useful if certain functionality of your command requires elevated
        permissions over the permissions it already requires by specification.
        """

        return self.responseHandle.getPermission()

    def isOwner(self) -> bool:

        """
        Check if the author of the message that invoked this command is the bot owner.
        This can be useful if certain functionality of your command requires elevated
        permissions over the permissions it already requires by specification.
        Returns True if the author is the owner, False otherwise.
        If the command was called from console, user ID check is skipped and this method will
        return True.
        If the bot ownership is not set in the config file and the command was issued from chat,
        this method will always return False.
        """

        if self.responseHandle.is_rpc():
            return True
        owner = self.config.getElementText("bot.owner", "")
        return owner == self.responseHandle.getID()

    def addArgument(self, argument: Argument):

        """
        Add an argument
        """

        assert isinstance(argument, Argument)
        self.arguments.append(argument)

    def addSubcommand(self, command: "Command"):

        """
        Add a subcommand to this command.
        """

        assert isinstance(command, Command)
        self.subcommands.append(command)

    def getUsage(self) -> str:

        """
        Get a usage string for the command e.g.
        "+test <arg1> [arg2]" 
        """

        cmds = [self.name]
        cmds.extend(self.aliases)

        prefix = environment.config.getElementText("bot.prefix","+")

        s = "**"+prefix+(", "+prefix).join(cmds)+"** "
        for i in self.arguments:
            if i.optional:
                s += "["+i.name+"] "
            else:
                s += "<"+i.name+"> "

        return s

    async def getHelp(self) -> str:

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

        if self.permissions != discord.Permissions.none() and self.responseHandle.is_chat():
            #permissions are required for this command, let the user know about it
            #This isn't relevant for console commands and is thus only printed if
            #the command was executed from chat
            if self.permissions.administrator:
                s += "\nThis command requires administrator permissions."
            else:
                perms = []
                for name, value in iter(self.permissions):
                    if value:
                        perms.append(name)
                s += "\nThis command requires the following permissions: `%s`" % ", ".join(perms)

        s += "\n\nUsage: "+self.getUsage()+"\n"

        if len(self.arguments) < 1:
            return s #skip argument header completely if we don't have any arguments

        s += "\nArguments:\n" #Give more information about arguments
        for i in self.arguments:
            s += "  '"+i.name+"' ("
            if i.optional:
                s += "optional"
            else:
                s += "required"
            s += ") type '"+i.__class__.__name__+"'\n"

        return s

    def _setVariables(self, responseHandle: "ResponseManager"):

        """
        Internal method.
        Sets the environment attributes
        """

        client = environment.client

        self.client = client
        self.config = client.config
        self.responseHandle = responseHandle
        self.msg = responseHandle.getMessage()
        self.db = client.db
        self.audioManager = client.audio