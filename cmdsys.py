#Discord ProtOS Bot
#
#Author: fredi_68
#
#Command subsystem

import logging
import enum
import importlib
import os
import asyncio

import discord

import chatutils
import cmdutils
import interaction
import traceback

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
    EMOTE = enum.auto() #TODO: Implement

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
SUPERUSERS = set()

logger = logging.getLogger("Command")

class CommandException(Exception):

    def __init__(self, msg, mention_user=False):

        self.mention_user = mention_user

class CommandCallFailedException(CommandException):

    pass

class CommandNotFoundException(CommandException):

    pass

class PermissionDeniedException(CommandException):

    pass

def cleanUpRegister(func, *args, **kwargs):

    """
    Register a function to be called at application exit.
    This is guaranteed to be called BEFORE the discord connection is terminated, unless the bot crashed.
    func must be an awaitable object.
    """

    logger.debug("Cleanup function registered: "+str(func))
    CLEANUP_FUNCTIONS.append([func,args,kwargs])

def loadModule(path):

    """
    Handles boilerplate code for importing a module from a file.
    Returns initialized module.
    Raises ImportError on failure.
    """

    spec = importlib.util.spec_from_file_location("command", path)
    if spec == None:
        raise ImportError("Unable to load spec for module %s" % path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

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

async def dialogConfirm(msg, client):

    """
    Ask the user to confirm an action.
    """

    await msg.channel.send(msg.author.mention+", "+interaction.confirm.getRandom())
    response = await client.wait_for_message(timeout=30, author=msg.author, channel=msg.channel)
    if not response: #message timed out, user took too long or didn't respond at all
        return
    if response.content.lower() in ["yes","yup","yee","ya","yas","yaaas","yeah","yea"]: #extend these if needed
        return True
    return

async def dialogReact(channel, user, client, message=None, emoji=None, timeout=30):

    """
    Wait for the user to select a chat message using an emoji.
    If emoji is given, it specifies the emoji that will trigger the dialog. Otherwise the dialog will trigger using any emoji.
    messsage specifies the promt the user is displayed with when starting the dialog. If ommitted, this will display a standard text.
    timeout specifies the time to wait for user input. Defaults to 30 seconds if ommitted.
    The returned value will be either of type discord.Message or None
    """

    def check(reaction, _user):

        if emoji and not reaction.emoji == emoji:
            return False

        if reaction.message.channel == channel and user == _user:
            return True
        return False

    message = message or "Please add " + (emoji.name if emoji else "an emoji ") + "to the message you want to select." #can't be more compact than that!

    await channel.send(message)
    reaction, user = await client.wait_for("reaction_add", check=check, timeout=timeout)
    return reaction.message

def loadCommands(path):

    """
    Load commands from a directory.
    """

    logger = logging.getLogger("cmdsys.loader")
    commands = []
    imports_failed = []
    for i in os.listdir(path):
        p = os.path.join(path, i)
        try:
            module = loadModule(p)
        except ImportError as e:
            imports_failed.append(i)
            logger.debug("Module import for file %s failed: %s" % (i, str(e)))
            continue
        except:
            imports_failed.append(i)
            logger.exception("An error occurred while loading external commands from %s: " % i)
            continue
        logger.debug("Loading command extension file %s..." % i)
        stuff = dir(module)
        for thing in stuff: #proper terminology is important
            try:
                thing = getattr(module, thing)
                if issubclass(thing, Command) and not thing == Command:
                    #looks like a command
                    try:
                        cmd = thing()
                    except BaseException as e:
                        logger.warn("Initializing command extension failed (source: %s): %s" % (i, str(e)))
                        logger.debug(traceback.format_exc())
                        continue
                    logger.debug("Registering command extension %s..." % cmd.name)
                    commands.append(cmd)
            except TypeError:
                pass
    logger.info("Done!\n")
    
    logger.info("%i external command(s) loaded. %i Errors:" % (len(commands), len(imports_failed)))
    for i in imports_failed:
        logger.warning("    -Unhandled exception caught while trying to import '"+i+"'")
    
    return commands

async def _processCommand(responseHandle, commands, config, client, databaseManager, audioManager, prefix, cmd, args):

    """
    Internal command parser.

    Raises various exceptions which are converted to messages by the processCommand wrapper function.
    """

    for i in commands:
        patterns = [i.name]
        patterns.extend(i.aliases) #we are looking for the command name as well as all aliases
        if cmd in patterns: #first word matches search pattern - this is the command we are looking for

            #is the user allowed to use this command?
            if not responseHandle.is_rpc():

                if not i.allowChat:
                    raise PermissionDeniedException("This command is not available in chat!")
                if i.ownerOnly and responseHandle.getID() != config.getElementInt("bot.owner"): #owner only command
                    if responseHandle.getID() == 181072803439706112:
                        raise PermissionDeniedException("Sorry Aidan, but I cannot let you do that.")
                    else:
                        raise PermissionDeniedException(interaction.denied.getRandom())
                if not (responseHandle.getID() in SUPERUSERS or responseHandle.getPermission().is_superset(i.permissions)): #insufficient permissions
                    raise PermissionDeniedException("You do not have sufficient permission to use this command.")

                #Is this user blocked?.
                if responseHandle.is_chat():
                    if responseHandle.getMessage().guild: #disabled for private messages
                        db = databaseManager.getServer(responseHandle.getMessage().guild.id)

                        ds = db.createDatasetIfNotExists("blockedUsers", {"userID": responseHandle.getMessage().author.id})
                        if ds.exists(): #FOUND YOU
                            raise PermissionDeniedException("You have been blocked from using bot commands. If you believe that this is an error please report this to the bot owner.")

            elif responseHandle.is_rpc():
                if not i.allowConsole:
                    raise PermissionDeniedException("This command is not available on console!")

            #process arguments

            #before searching arguments, see if there are any subcommands
            if i.subcommands:
                #is the user trying to call a subcommand?
                try:
                    await _processCommand(responseHandle, i.subcommands, config, client, databaseManager, audioManager, "", args[0], args[1:])
                except CommandNotFoundException as e:
                    #that would be a no
                    pass
                else:
                    #subcommand handled user call, return
                    return

            #first, check if we have the right amount of arguments.
            argamt = len(args)
            oblargs = [] #obligatory arguments (we will need these later)
            optargs = [] #optional arguments

            for j in i.arguments:

                optargs.append(j) if j.optional else oblargs.append(j) #sort between optinal and non optional arguments

            if argamt < len(oblargs): #not enough arguments

                #set environment attributes for external commands
                i._setVariables(client, config, responseHandle, databaseManager, audioManager)
                raise CommandCallFailedException("Not enough arguments\n" + i.getUsage())

            else:

                #correct amount of arguments, next we check argument types
                #We will assume that all arguments have to be entered in the same sequence as specified in the commad
                #We also assume that all optional arguments are entered AFTER the obligatory ones so we will just raise an exception if they don't
                #And we also assume that all optional arguments require earlier optional arguments to be included
                #Any arguments left at the end will be consumed by the last argument

                #TODO: Add support for command flags and subcommands (Maybe a modified Command class for this?)

                arguments = {}

                for j in range(0, len(args)):
                    
                    arg = args[j]
                    if j >= len(i.arguments):
                        break #we done
                    elif j >= len(i.arguments) - 1:
                        #only one left... better make it count
                        arg = " ".join(args[j:]) #make one large argument consuming the rest of the argstring
                    errorStr = "Illegal argument type for " + i.arguments[j].name + ": "
                    t = i.arguments[j].type

                    if t == CmdTypes.INT:
                        try:
                            arguments[i.arguments[j].name] = int(arg)
                        except:
                            raise CommandCallFailedException(errorStr+" Type Int expected!")

                    elif t == CmdTypes.FLOAT:
                        try:
                            arguments[i.arguments[j].name] = float(arg)
                        except:
                            raise CommandCallFailedException(errorStr + " Type Float expected!")

                    elif t == CmdTypes.STR or t == CmdTypes.EMOTE:
                        arguments[i.arguments[j].name] = str(arg) #this one doesn't need any processing, however, we don't want the command to modify this directly

                    elif t == CmdTypes.BOOL:
                        if arg.lower() in ["True", "true", "1"]:
                            arguments[i.arguments[j].name] = True
                        elif arg.lower() in ["False", "false", "0"]:
                            arguments[i.arguments[j].name] = False
                        else:
                            raise CommandCallFailedException(errorStr + " Type Bool expected!")

                    elif t == CmdTypes.MESSAGE:
                        if arg.lower() == "react":
                            if not responseHandle.is_chat():
                                raise CommandCallFailedException("Reaction selecting is not possible for console commands!")
                            message = await dialogReact(responseHandle.getMessage().channel, responseHandle.getMessage().author, client, "Please react to the message you are trying to select with an emoji of your choice.")
                            if not message:
                                return #something went wrong, most likely a timeout
                            arguments[i.arguments[j].name] = message #reaction selector worked, arg parsing done
                            continue

                        if ":" in arg and i.allowDelimiters:
                            #NEW FEATURE!
                            #by using a colon to separate a channel and message ID we can specify a specific message in a specific channel
                            ch, msg = list(map(int, arg.split(":", 1)))
                            try:
                                arguments[i.arguments[j].name] = await client.get_channel(ch).fetch_message(msg)
                            except:
                                raise CommandCallFailedException(errorStr + " Not a valid channel:message ID!")
                            continue

                        try:
                            arguments[i.arguments[j].name] = await responseHandle.getMessage().channel.fetch_message(int(arg)) #This was an oversight on my part. The current implementation REQUIRES the message to be in the same channel as the caller (thus won't work on console)
                        except:
                            raise CommandCallFailedException(errorStr + " Not a valid message ID!")

                    elif t == CmdTypes.CHANNEL:
                        if arg.lower() == "post":
                            if not responseHandle.is_chat():
                                raise CommandCallFailedException("Post selecting is not possible for console commands!")
                            await responseHandle.reply("Please post a message in the channel you are trying to select. It will be automatically deleted.")
                            message = await client.wait_for_message(author=responseHandle.getMessage().author, timeout=30)
                            if not message:
                                responseHandle.close()
                                return #again, probably timed out
                            arguments[i.arguments[j].name] = message.channel #post selector worked, arg parsing done
                            try:
                                await client.delete_message(message) #get rid of the message the user posted to select
                            except discord.HTTPException:
                                pass
                            continue

                        ret = chatutils.getChannelMention(arg)
                        if ret:
                            arg = ret
                        else:
                            try:
                                arg = int(arg)
                            except ValueError:
                                pass

                        try:
                            arguments[i.arguments[j].name] = client.get_channel(arg)
                        except:
                            raise CommandCallFailedException(errorStr + " Not a valid channel ID!")

                    elif t == CmdTypes.SERVER:
                        try:
                            arguments[i.arguments[j].name] = client.get_server(int(arg))
                        except:
                            raise CommandCallFailedException(errorStr + " Not a valid server ID!")

                    elif t == CmdTypes.MEMBER:

                        if ":" in arg and i.allowDelimiters:
                            #We can save this by specifying a new format, using a colon to denote server and member ID:
                            srv, mem = list(map(int, arg.split(":", 1)))
                            try:
                                arguments[i.arguments[j].name] = client.get_server(srv).get_member(mem)
                            except:
                                raise CommandCallFailedException(errorStr + " Not a valid server:member ID!")
                            continue

                        if not responseHandle.is_chat():

                            arguments[i.arguments[j].name] = arg #can't do anything about it on console
                            continue

                        ret = chatutils.getMention(arg)
                        if ret:
                            arg = ret #substitute the mention with the user ID. This SHOULD work given that our RE is actually correct
                        else:
                            try:
                                arg = int(arg)
                            except ValueError:
                                pass
                        try:
                            arguments[i.arguments[j].name] = responseHandle.getMessage().guild.get_member(arg) #we assume the user means this server
                        except:
                            arguments[i.arguments[j].name] = arg

                    elif t == CmdTypes.USER:

                        #TODO:
                        #This is a bit tricky. Usually discord users only have access to the user profiles that they are either
                        #   a) friends with or
                        #   b) in the same server with
                        #Bot accounts are special in this regard, since they can access ANY USER PROFILE THEY CHOOSE, AS LONG AS THEY HAVE THE ID.
                        #This gets a bit difficult if we are running an actual user account. To get access to a user JUST by their ID we could do
                        #one of the following:
                        #   a) search our friend list and all servers we are in for a user with the same ID (which would take ages) OR
                        #   b) get a separate bot account JUST for actions that require a bot account. This would require this account to be somewhere in
                        #      a server and a separate client to be created on startup. This would also make our login procedure more complicated.

                        if not responseHandle.is_chat():

                            arguments[i.arguments[j].name] = arg #can't do anything about it on console
                            continue

                        ret = chatutils.getMention(arg) #can still use mentions to get user IDs...
                        if ret:
                            arg = ret
                        else:
                            try:
                                arg = int(arg)
                            except ValueError:
                                pass
                        if client.user.bot:
                            try:
                                arguments[i.arguments[j].name] = client.get_user_info(arg) #...but this doesn't work anymore
                            except:
                                arguments[i.arguments[j].name] = arg
                        else:
                            #For now, implement version a)

                            users = list(client.get_all_members())
                            if responseHandle.getMessage().channel.is_private:
                                users.extend(responseHandle.getMessage().channel.recipients) #additionally include users in current DM channel (cause friendslist is broken)
                            userFound = False
                            for user in users:
                                if user.id == arg:
                                    arguments[i.arguments[j].name] = user
                                    userFound = True
                                    break

                            if not userFound:
                                raise CommandCallFailedException(errorStr + " User can't be found.")

                    elif t == CmdTypes.ROLE:

                        if ":" in arg and i.allowDelimiters:
                            srv, role = list(map(int, arg.split(":", 1)))
                            try:
                                arguments[i.arguments[j].name] = chatutils.getRole(client.get_server(srv), role)
                            except:
                                raise CommandCallFailedException(errorStr + " Not a valid server:role ID!")
                            continue

                        if not responseHandle.is_chat():

                            arguments[i.arguments[j].name] = arg #can't do anything about it on console
                            continue

                        ret = chatutils.getRoleMention(arg)
                        if ret:
                            arg = ret #substitute the mention with the role ID. This SHOULD work given that our RE is actually correct
                        else:
                            try:
                                arg = int(arg)
                            except ValueError:
                                pass

                        try:
                            arguments[i.arguments[j].name] = chatutils.getRole(responseHandle.getMessage().guild, arg) #we assume the user means this server
                        except:
                            arguments[i.arguments[j].name] = arg

                    else: #Since we don't have all types setup right now just copy stuff we can't check. The command is responsible for handling these cases
                        arguments[i.arguments[j].name] = arg

                #set environment variables for external commands
                i._setVariables(client, config, responseHandle, databaseManager, audioManager)
                #call command
                await i.call(**arguments)

            return #exit command handler

    raise CommandNotFoundException("That command doesn't exist.") #if we don't find a command let the user know about it

async def processCommand(responseHandle, commands, config, client, databaseManager, audioManager):

    """
    Interface for unified command handling
    """

    cmd_prefix = config.getElementText("bot.prefix", "+")

    icons = { #Discord chat icons
        "ok": config.getElementText("bot.icons.ok"),
        "forbidden": config.getElementText("bot.icons.forbidden"),
        "error": config.getElementText("bot.icons.error"),
        "pin": config.getElementText("bot.icons.pin")
        }

    content = await responseHandle.getCommand()
    if responseHandle.is_chat():
        content = content[len(cmd_prefix):] #get the content of the message (without the prefix)

    #Separate the words for convenience
    words = chatutils.splitCommandString(content)
    if len(words) < 1:
        responseHandle.close()
        return #not enough words - empty message?

    if words[0] in ["help", "h", "?"]: #SPECIAL CASE: This command is hardcoded since it needs access to all other commands
        if len(words) > 1: #The user wants help on a specific command
            for i in commands:
                if i.name == words[1] and not i.hidden: #make sure hidden commands don't come up in the search
                    #set environment variables for external commands
                    i._setVariables(client, config, responseHandle, databaseManager, audioManager)
                    await responseHandle.reply(await i.getHelp(), False) #generate help information and send it to the user
                    responseHandle.close()
                    return
            await responseHandle.reply(icons["error"] + " That command does not exist.", True)
        else:
            #print ALL commands and their usages
            hs = "commands:\n\n"
            maxlen = 20 #maximum size of commands
            for i in commands:
                if i.hidden:
                    continue #make sure hidden commands don't come up in the search

                #set environment variables for external commands
                i._setVariables(client, config, responseHandle, databaseManager, audioManager)

                #calculate length of command string
                spacing = max(1, maxlen - (len(cmd_prefix) + len(i.name))) #how many spaces do we need to fill? Also guarantee at least one space
                hs += cmd_prefix + i.name + " " * spacing + i.getUsage() + "\n"

            spacing = max(1, maxlen - (len(cmd_prefix) + 4))
            hs += cmd_prefix + "help" + " " * spacing + "Usage: +help, +h, +? -> Get this help page :D"
            await responseHandle.reply(hs, False) #generate help information and send it to the user
        responseHandle.close()
        return

    try:
        await _processCommand(responseHandle, commands, config, client, databaseManager, audioManager, cmd_prefix, words[0], words[1:])
    except CommandException as e:
        await responseHandle.reply(icons["error"] + " " + str(e), e.mention_user)
    except BaseException as e:
        logging.exception("Command execution failed: ")
        if config.getElementInt("bot.debug.showCommandErrors", 0, False):
            tb = chatutils.mdEscape(traceback.format_exc())
            await responseHandle.reply("Command execution failed:\n %s\n\nYou are receiving this message because command debugging is enabled.\nIt can be disabled in the config files." % tb, True)

    responseHandle.close()

class Argument():

    def __init__(self, name, type=CMD_TYPE_INT, optional=False, default=None):

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
        Base class for all commands.
        This class needs to be subclassed to implement actual functionality.

        Please refer to commands/commands.TXT for more information
        """

        self.logger = logging.getLogger("Uninitialized Command")

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

        db = self.db.getServer(self.msg.guild.id)
        dsList = db.enumerateDatasets("auditLogChannels")
        for i in dsList:
            dch = self.msg.guild.get_channel(i.getValue("channelID"))
            await dch.send(msg)

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

    def getAuthorPermissions(self):

        """
        Return the discord.Permissions object associated with the author of
        the message that invoked this command.
        This can be useful if certain functionality of your command requires elevated
        permissions over the permissions it already requires by specification.
        """

        return self.responseHandle.getPermission()

    def isOwner(self):

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

    def addArgument(self, argument):

        """
        Add an argument
        """

        assert isinstance(argument, Argument)
        self.arguments.append(argument)

    def addSubcommand(self, command):

        """
        Add a subcommand to this command.
        """

        assert isinstance(command, Command)
        self.subcommands.append(command)

    def getUsage(self):

        """
        Get a usage string for the command e.g.
        "Usage: +test <arg1> [arg2]" 
        """

        cmds = [self.name]
        cmds.extend(self.aliases)

        prefix = self.config.getElementText("bot.prefix","+")

        s = "Usage: **"+prefix+(", "+prefix).join(cmds)+"** "
        for i in self.arguments:
            if i.optional:
                s += "["+i.name+"] "
            else:
                s += "<"+i.name+"> "

        return s

    async def getHelp(self):

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

        s += "\n\n"+self.getUsage()+"\n"

        if len(self.arguments) < 1:
            return s #skip argument header completely if we don't have any arguments

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