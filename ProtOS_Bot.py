#Discord ProtOS Bot
#Codename: Ram
#
#Author: fredi_68
#

#IMPORTS

#Standard library
import platform
import asyncio
import time
import re
import os
import sys
import traceback
import subprocess
import random
import logging
import logging.config #needs to be imported separately
import wave
import functools
import json
import importlib
import importlib.util
import ctypes
import ctypes.util

#Third party
import discord

HAS_YTDL = True
try:
    import youtube_dl #Try to import youtube_dl, this is an optional package used to play YouTube videos using the play command
except ImportError:
    HAS_YTDL = False

if sys.path[0]: #set cwd in case that the script was started from a different directory than the bot root
    try:
        os.chdir(sys.path[0]) #this needs to be done before any app level modules are imported to prevent ImportErrors
    except NotADirectoryError:
        pass #This can happen if we are running the application in an environment that is not a filesystem (for example, a frozen binary distribution)

#Application
import cmdutils
import twitch
import version
import config
import chatutils
import interaction
import audio
import conversation

from cmdsys import *

#Set up logging
try:
    import fixLogging #monkey patch logging module to support positional arguments
except ImportError:
    #Can't commit this to remote cause copyright
    pass
#make sure the logging directory exists, since it doesn't get created by the patcher and logging doesn't like that
os.makedirs("logs", exist_ok=True)
if not os.path.isfile("config/logging.json"):
    #Do print() logging here since our logger is not configured yet
    print("[SETUP] WARNING: Logging configuration not found. Creating default config...")
    defaultConfig = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "form_default": {
                "format": "[%(asctime)s][%(name)s][%(levelname)s]: %(message)s",
                "level": "DEBUG",
                "datefmt": None
                }
            },
        "filters": {
            },
        "handlers": {
            "hand_console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "form_default",
                "stream": "ext://sys.stdout"
                },
            "hand_default": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "form_default",
                "filename": "logs/ProtOS_Bot.log",
                "when": "midnight",
                "backupCount": 10,
                "interval": 1
                }
            },
        "loggers": {
            },
        "root": {
            "handlers": ["hand_console", "hand_default"],
            "level": "DEBUG"
            }
        }
    with open("config/logging.json", "w") as f:
        json.dump(defaultConfig, f, indent=4)
        
with open("config/logging.json", "r") as f:
    logging.config.dictConfig(json.load(f))

#Title print

logging.info(cmdutils.formatText(version.S_TITLE_VERSION, bold = True))
cmdutils.printSeparator()

logging.info("Loading modules...")

#Setup

CONFIG_MANAGER = config.configManager("config/bot.xml", requireVersion=1)
DATABASE_MANAGER = config.DatabaseManager()

if not CONFIG_MANAGER.getElementText("bot.owner", ""): #Let the user know if he forgot to set bot ownership, since this can be quite the severe issue if the bot isn't running a console of any kind
    logging.getLogger("Config").warn("Bot ownership not set! Please review your configuration files!")

#OPUS library loading

#[WIN]
#we've got a 64bit system; since discord.py is very picky about the location and the name of the opus library,
#change the default to make sure users without a config don't run into problems

#[LINUX/UNIX]
#we use the library finder to locate the shared library, if no explicit name was specified in the config file.
#If the loader can't find the library, default back to the standard windows path.
logger = logging.getLogger("Discord")
logger.info("Loading Opus...")
libArch = 32
if platform.architecture()[0] == "64bit": 
    libArch = 64
opusPath = CONFIG_MANAGER.getElementText("bot.opus.path", "")
if not opusPath:
    logger.debug("Missing OPUS shared library path in config file, trying to automatically locate library...")
    opusPath = ctypes.util.find_library("opus")
    if not opusPath:
        logger.debug("Unable to locate OPUS library, trying default location...")
        opusPath = "bin/opus/opus%i" % libArch
discord.opus.load_opus(opusPath)

#Post init module import

interaction.init()
import voicecom

QUOTE_MANAGER = interaction.QuoteManager("chat/quotes/")

#HELPER FUNCTIONS

_ver = list(map(int,platform.python_version_tuple())) #get python version tuple as int list
HAS_UTF8 = ((_ver[0] == 3 and _ver[1] > 5 ) or _ver[0] > 3) #Python version 3.6 introduces console UTF-8 support, enable if possible

def logMessage(msg):

    """
    Logs the message to the console window.
    Includes pretty printer options for server, channel, names/nicknames and role color
    """
    
    logger = logging.getLogger("MessageLog")

    
    s = cmdutils.translateString(msg.content)
    a = cmdutils.translateString(msg.author.name)
    if hasattr(msg.author, "nick") and msg.author.nick:
        a = cmdutils.translateString(msg.author.nick) + "/" + a
        
    for i in msg.attachments: #display attachments
        s += "\n    => with attachment:"
        for j in i.items():
            s += "\n       " + j[0] + ": " + str(j[1])

    if msg.channel.is_private: #We received a DM instead of a server message, this means most of our code is not required
            
        name = msg.channel.recipients[0].name if not msg.channel.name else msg.channel.name
        logger.info("[DM][%s](%s): %s" % (name, a, s))
        return

    color = msg.author.colour.to_tuple() if hasattr(msg.author, "colour") else (0, 0, 0)
    logger.info("[%s][%s](%s): %s" % (msg.server.name, msg.channel.name, cmdutils.colorText(a, color), s))

def changeRecordingState(ch):

    """
    EXPERIMENTAL FEATURE! This method starts or stops audio recording on a channel.
    """

    logger = logging.getLogger("Audio")
    if ch.id in SOUNDS_RECORDING: #we are already recording on this channel, stop the recording
        SOUNDS_RECORDING[ch.id].stop()
        del SOUNDS_RECORDING[ch.id] #remove the FileRecorder from the dict
    else:
        filename = "sounds/recordings/%s_%s.wav" % (ch.name, time.strftime("%Y-%m-%d_%H-%M-%S"))
        SOUNDS_RECORDING[ch.id] = FileRecorder(CONNECTIONLISTENER, ch, filename, None)

class ResponseManager():

    #Discord hard limits message length. For long responses, we want to automatically
    #split up the payload into chunks of the specified length.
    CHAT_CHARACTER_LIMIT = 2000

    def __init__(self, client=None, msg=None, reader=None, writer=None):

        """
        Response Manager class
        This class abstracts command responses from the user by supplying a unified interface that will do "the right thing".
        If the command was issued via chat post, this will output to the channel the message was received from.
        If the command was issued by a RPC, this will accumulate the results and send them to the caller.
        Users should either supply both client and chat or reader and writer as keyword arguments.
        If all arguments are present, both behaviours will be executed subsequently.
        """

        self.logger = logging.getLogger("Response Manager")

        if not ((client and msg) or (reader and writer)):
            raise ValueError("User must specify either client and msg or reader and writer instances")

        self.is_closed=False
        self.client = client
        self.msg = msg
        self.reader = reader
        self.writer = writer

        self.rpc_messages = []
        self.chat_messages = []

    def getMessage(self):

        """
        Returns the original message object.
        If the command was not issued through chat, this method will return None.
        """

        return self.msg if self.is_chat() else None

    async def getCommand(self):

        """
        Returns the original command message. This will include the prefix of chat commands.
        If the command can not be determined this method will return an empty string.
        """

        if self.is_rpc():
            return (await self.reader.readline()).decode() #get command and convert it to str
        elif self.is_chat():
            return self.msg.content
        return ""

    def getPermission(self):

        """
        Returns the permissions for the command issuer. For RPCs this will always be administrator level.
        If the permission level can not be determined this method will return a Permissions object with no permissions.
        """

        if self.is_rpc():
            p = discord.Permissions.all() #Give RPC calls all permissions, regardless of accessed area
            return p
        #make sure that user permissions are only retrieved from discord if we are in a public server (admin commands should not work in DMs)
        elif self.is_chat() and self.msg.channel.type == discord.ChannelType.text:
            local_permissions = self.msg.author.permissions_in(self.msg.channel)
            try:
                server_permissions = self.msg.author.server_permissions
            except:
                server_permissions = discord.Permissions.none()
            return discord.Permissions(local_permissions.value | server_permissions.value) #union both permissions
        #if everything fails, we return a safe permissions object without any permissions
        return discord.Permissions.none()

    def getID(self):

        """
        Returns the ID of the command issuer. For RPCs this will always be 1.
        If the ID can not be determined this method will return None
        """

        if self.is_rpc():
            return "1" #ensure compatability with chat commands
        elif self.is_chat():
            return self.msg.author.id
        return None

    async def reply(self, msg, mention=False, flush_chat=True):

        """
        Send a response message to the command issuer.
        mention specifies if the targeted user should be mentioned and is
            ignored if the command was executed via RPC.
        Output is automatically buffered for RPC calls.
        If flush_chat is True, the message will be dispatched immediately. It is ignored for RPC calls.

        WARNING: Setting flush_chat to False will buffer messages until the ResponseManager is GCed OR another call to reply()
        is made with flush_chat set to True (in this case, all messages will be dispached in order).
        If you don't manually flush your messages at least once after setting flush_chat to False, they will be sent after an
        indefinite amount of time. If you sent messages with flush_chat=False, you should consider calling flush() to ensure that
        the messages are dispatched correctly.

        WARNING: If your message is longer than Discords internal character limit (currently 2000 characters per message) it
        may not send properly. The ResponseManager will attempt to split up messages that are longer than the character limit,
        however, this does not work in specific cases. For example, sending a message with a single line of more than 2000 characters
        will fail. Also, sending very long messages of over 5x the character limit may take severely longer due to Discord internal rate
        limiting. There is no way of cicumventing this behavior, so keep it short.

        If you try to send a message larger than 2000 characters a warning will be logged.
        """

        if self.is_rpc():
            self._RPCReply(msg)

        if self.is_chat():

            if len(msg) > self.CHAT_CHARACTER_LIMIT:
                self.logger.warn("Message is over character limit, message may fail to send properly")

            for line in msg.split("\n"):
                await self._ChatReply(line, mention, False)
                mention = False #if mention was set, it will be in the first line, but no subsequent ones
            if flush_chat:
                await self._ChatReply("", False, True)

    async def createEmbed(self, embed):

        """
        Send a response message to the command user using an Embed object.
        If the command was executed via RPC,
        embed behaviour will be emulated using ASCII characters.
        """

        if self.is_rpc():
            self._RPCCreateEmbed(embed)

        if self.is_chat():
            await self._ChatCreateEmbed(embed)

    def is_rpc(self):

        """
        Check if the message was send via RPC
        """

        return self.reader and self.writer

    def is_chat(self):

        """
        Check if the message was send via chat
        """

        return self.client and self.msg

    def _RPCReply(self, msg):

        if not msg:
            return

        self.rpc_messages.append(msg)
        self.logger.info(msg) #log message to screen

    async def _ChatReply(self, msg, mention, flush_chat):

        ret = self.msg.author.mention + ", " + msg if mention else msg #add a mention to the response if requested
        self.chat_messages.append(ret)

        if flush_chat:

            #if we don't have any messages, exit
            while len(self.chat_messages) > 0:
                ret = ""

                #if we run out of messages, finish this batch then exit
                while len(self.chat_messages) > 0:

                    if len(ret) + len(self.chat_messages[0]) > self.CHAT_CHARACTER_LIMIT:
                        if not ret: #This can happen when a single message is too large to be sent
                            #If this happens, it's the users fault, since we cannot split the message up
                            #without causing issues. We will attempt to send it but it WILL fail.
                            #Let the error propagate.
                            await self.client.send_message(self.msg.channel, self.chat_messages.pop(0))
                        break

                    ret += self.chat_messages.pop(0) #get next message and add it to the buffer.
                    ret += "\n" #add newline to separate messages
                                        #Don't go over the character limit

                #we want to avoid empty messages and always append a newline so we check for messages smaller than 2 characters
                ret = ret.rstrip("\n") #strip last newline
                if len(ret) > 0:
                    await self.client.send_message(self.msg.channel, ret) #send message

    def _RPCCreateEmbed(self, embed):

        """
        Internal method.
        Emulates a Discord embed using a text only interface.
        """

        title = str(embed.title)
        desc = str(embed.description)
        footer = str(embed.footer.text)
        author = str(embed.author.name)

        self.rpc_messages.append("Rich Embed:\n"+"="*60+"\n")
        self.rpc_messages.append("%s | %s\n" % (title, desc))
        for i in embed.fields:
            self.rpc_messages.append("\n"+i.name)
            self.rpc_messages.append("\n"+"-"*40)
            self.rpc_messages.append("\n"+i.value+"\n")

        if embed.footer != embed.Empty:
            self.rpc_messages.append("\n%s | %s" % (footer, author))

    async def _ChatCreateEmbed(self, embed):

        """
        Internal method.
        Send an empty message to Discord, with the embed attached.
        Output is NOT buffered.
        """

        await self.client.send_message(self.msg.channel, "", embed=embed)

    async def flush(self):

        """
        Flushes the internal message buffer.
        For RPC, this is currently a no-op, as multipart messages are not implemented yet.
        """

        await self.reply("", False, True) #flush the chat message buffer

    def close(self):

        """
        This method should always be called after the command has been executed, even in case of failure. If the command
        was issued by a RPC, this will accumulate all messages, send them to the caller and then close all streams and perform
        cleanup.
        It is safe to call this method more than once.
        This method is automatically called on object GC to make sure ressources get freed properly.
        """

        if self.is_closed:
            return

        if self.is_chat():
            self.client.loop.create_task(self.flush()) #flush internal message buffer

        if self.is_rpc():
            #write response
            lines = map(str.encode, self.rpc_messages) #encode to bytes
            returnString = b" ".join(lines)
            if not returnString:
                returnString = b"Internal error: No response."
            try:
                self.writer.write(returnString)
            except IOError:
                self.logger.exception("IO Exception occured while trying to write RPC response:")
            #close RPC connection
            try:
                if hasattr(self.writer, "can_write_eof") and self.writer.can_write_eof():
                    self.writer.write_eof() #close the stream the "nice" way
                else:
                    self.logger.warning("Stream doesn't support write_eof()... this could lead to a hang in the RAT process")
                self.writer.close()
            except (IOError, OSError, AttributeError):
                self.logger.exception("Error occured while trying to close the RPC connection:")

        self.is_closed = True

    def __del__(self):

        #This can raise errors if the objects gets GCed while the interpreter is shutting down.
        #To prevent crashes after asyncio has shut down, we suppress any relevant errors this
        #call could raise since this is a clean up method and not that important
        try:
            self.logger.debug("Response handle is about to be destroyed, ensuring closed connections")
        except AttributeError:
            pass

        try:
            self.close()
        except:
            pass

class FileRecorder():

    def __init__(self, listener, channel, file, callback=None):

        """
        Create a new voice chat recorder that will immediately start recording audio into the specified file.
        To stop recording audio, call the stop method. An optional callback callable will be called after clean up.
        """

        self.file = wave.open(file,"wb")
        self.channel = channel
        self._recording = False
        self.bufferSize = 1024 #may be a little small but we'll see

        self.listener = listener

        self.logger = logging.getLogger("RECORDER")

        self.callback = callback

        client.loop.create_task(self._record()) #Run the recorder

    async def _configureFile(self):

        """
        Configure the wave file handler to handle our PCM stream data correctly
        """

        #Discord always uses 2 channels at 48000hz.
        #The sample width should be 2 (16bit) but for some reason it isn't working correctly, we will need to experiment with this
        self.file.setnchannels(2)
        self.file.setframerate(48000)
        self.file.setsampwidth(2)

    async def _record(self):

        """
        Recording subroutine.
        This method runs until the stop method is called and continuously writes voice data to the file.
        """

        await self._configureFile()
        self._recording = True
        self.logger.info("Recording audio from channel " + self.channel.name)
        while self._recording:

            try:
                data = await self.listener.getAudio(self.channel, self.bufferSize)
                if data:
                    self.logger.debug("Got audio data: " + str(len(data)) + " byte(s) recorded.")
                    self.file.writeframes(data)
            except ValueError:
                self.logger.error("Channel not found, stopping recording")
                break #channel doesn't exist, stop recording
            await asyncio.sleep(0.01) #add minimal delay to ensure that the program stays responsive

        #recording finished
        self.logger.info("Recording finished, cleaning up...")
        self.file.close()
        if self.callback:
            self.callback()

    def stop(self):

        self._recording = False

#COMMANDS

logging.getLogger("Command").info("Loading internal commands...")

CMD_PREFIX = CONFIG_MANAGER.getElementText("bot.prefix", "+")

COMMANDS = []

#With the new command subsystem in cmdsys.py we can now move all the simple commands to different files which makes this programm a lot easier to read.
#Because some commands are deeply integrated into the inner workings of the bot though, I've decided to separate commands into "internal" and "external" commands.
#The internal commands can be found here. The external commands are located in the command folder in the bot directory.

class CmdQuit(Command):

    def setup(self):

        self.name = "quit"
        self.desc = "Shut the bot down."
        self.ownerOnly = True

    async def call(self, **kwargs):
        
        #Run clean up functions
        await cleanUp()

        #Save configuration
        await save()
        #close connection to discord
        await client.logout()
        await client.close()
        #client.loop.stop()
        #client.loop.close()
        #sys.exit()

COMMANDS.append(CmdQuit())

class CmdVoice(Command):

    def setup(self):

        self.name = "voice"
        self.desc = "Makes the bot join voice chat."
        self.addArgument(Argument("channel", CmdTypes.STR, True))

    async def call(self, channel=None, **kwargs):

        if not self.msg:
            if not channel:
                await self.respond("Channel specification is required for using this command on console!")
                return
        else:
            if not channel:
                if not self.msg.author.voice_channel:
                    await self.respond("You are not in a voice channel. Please specify a channel for me to connect to.", True)
                    return
                channel = self.msg.author.voice_channel.id
        channel = client.get_channel(channel)
        await self.respond("Joining channel now...", True)
        try:
            await client.join_voice_channel(channel)
        except discord.errors.DiscordException:
            await self.respond("Failed to join voice channel.", True)
            return

        #Load audio configuration for server
        db = self.db.getServer(self.msg.server.id)
        db.createTableIfNotExists("voiceClientSettings", {"name": "text", "value": "text"})
        ds = db.createDatasetIfNotExists("voiceClientSettings", {"name": "volume"})
        if not ds.exists():
            return

        volume = ds.getValue("value")
        if volume in (None, "None"): #Some dataset weirdness
            return

        ch = self.audioManager.createChannel(channel)
        ch.setVolume(float(volume))

        return

COMMANDS.append(CmdVoice())

class CmdLeave(Command):

    def setup(self):

        self.name = "leave"
        self.desc = "Makes the bot leave the voice channel."
        self.permissions.administrator = True
        self.addArgument(Argument("server", CmdTypes.SERVER, True))

    async def call(self, server=None, **kwargs):

        if not self.msg:
            if not server:
                await self.respond("Server specification is required for using this command on console!")
                return
        else:
            if not server:
                server = self.msg.server

        if not client.voice_client_in(server):
            await self.respond("Not currently connected to any voice channels on this server.", True)
            return

        await self.respond("Disconnecting, please stand by.", True)
        try:
            self.audioManager.shutdownChannel(server.voice_client.channel) #stop all sounds that are still playing
        except audio.AudioError:
            pass
        await server.voice_client.disconnect() #we need to do this after stopping the sounds, otherwise voice_client is set to None

COMMANDS.append(CmdLeave())

class CmdQuote(Command):

    def setup(self):

        self.name = "quote"
        self.aliases.append("qt")
        self.desc = "Access member quote storage."
        self.addArgument(Argument("user", CmdTypes.STR, True))
        self.addArgument(Argument("mode", CmdTypes.STR, True))
        self.addArgument(Argument("quote", CmdTypes.STR, True))

    async def call(self, user=None, quote=None, mode=None, **kwargs):

        if not user:
            q = QUOTE_MANAGER.getRandom()
            if not q:
                await self.respond("I don't know any quotes yet. Try adding some using 'quote add'!", True)
                return
            await self.respond(q)
            return
        if mode == "add":
            if not quote:
                await self.respond("You have to specify a message to add as a quote!", True)
                return
            i = QUOTE_MANAGER.addQuote(user.lower(), quote)
            if i or isinstance(i, int):
                await self.respond("Successfully added quote!", True)
                return
            await self.respond("Failed to add quote.", True)
            return
        if mode:
            try:
                mode = int(mode)
            except:
                await self.respond("Not a valid quote index!", True)
                return
            q = QUOTE_MANAGER.getQuote(user.lower(), mode)
            if q:
                await self.respond(q)
            return
        q = QUOTE_MANAGER.getRandomByName(user)
        if q:
            await self.respond(q)
        return

COMMANDS.append(CmdQuote())

class CmdVoiceDebug(Command):

    def setup(self):

        self.name = "enableVoiceLog"
        self.desc = "HIGHLY EXPERIMENTAL. Start recording voice input and save it do the disk. If voice recording is already activated for this channel, stop recording and flush the buffer to the file."
        self.ownerOnly = True
        self.hidden = True

    async def call(self, **kwargs):

        if not (hasattr(self.msg.server, "voice_client") and self.msg.server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return
        changeRecordingState(self.msg.server.voice_client.channel)

COMMANDS.append(CmdVoiceDebug())

class CmdNickLock(Command):

    def setup(self):

        self.name = "setNickLock"
        self.desc = "Set the nickname lock state."
        self.ownerOnly = True
        self.hidden = True
        self.addArgument(Argument("state", CmdTypes.BOOL))

    async def call(self, state, **kwargs):

        global NICKNAME_LOCKED
        NICKNAME_LOCKED = state

COMMANDS.append(CmdNickLock())

class CmdSave(Command):

    def setup(self):

        self.name = "save"
        self.aliases.append("backup")
        self.ownerOnly = True
        self.hidden = True

    async def call(self, **kwargs):

        await self.respond("Creating backup...")
        await save()
        await self.respond("Backup complete!")

COMMANDS.append(CmdSave())

class CmdStats(Command):

    def setup(self):

        self.name = "stats"
     
    async def call(self, **kwargs):

        e = discord.Embed(title="ProtOS Bot Statistics")

        has_imglib = True
        try:
            import imagelib
            imagelib.init(do_raise=True)
            del imagelib
        except:
            has_imglib = False

        generalInformation = (
            "Name: %s    " % client.user.name,
            "UID: %s    " % client.user.id,
            "Version: %s    " % version.S_VERSION,
            "Shard: %i/%i    " % ((client.shard_id if client.shard_id else 0)+1, (client.shard_count if client.shard_count else 1)),
            "AI Backend: %s" % (CONVERSATION_SIMULATOR.name),
            "Music Backend: %s" % ("youtube_dl" if HAS_YTDL else "Unavailable"),
            "Image Processing Backend: %s" % ("imagelib" if has_imglib else "Unavailable")
            )
        e.add_field(name="General Information:", value="\n".join(generalInformation), inline=True)

        discordInformation = (
            "Discord.py Version: %s" % discord.__version__,
            "Server Count: %i    " % len(list(client.servers)),
            "Member Count: %i    " % len(list(client.get_all_members())),
            "Channel Count: %i    " % len(list(client.get_all_channels())),
            "Emoji Count: %i    " % len(list(client.get_all_emojis()))
            )
        e.add_field(name="Discord Related:", value="\n".join(discordInformation), inline=True)

        aiState = self.config.getElementText("bot.chat.aistate", "unknown", False).upper()

        settings = (
            "AI State: %s" % aiState,
            "Voice Receive Hooks: %s" % ("Enabled" if USE_VOICECOM else "Disabled")
            )
        e.add_field(name="Settings:", value="\n".join(settings), inline=True)

        await self.embed(e)

COMMANDS.append(CmdStats())

class CmdVersion(Command):

    def setup(self):

        self.name = "version"

    async def call(self, **kwargs):

        await self.respond(version.S_TITLE_VERSION)

COMMANDS.append(CmdVersion())

class CmdCSOpt(Command):

    def setup(self):

        self.name = "csopt"
        self.aliases.append("csoption")
        self.aliases.append("csoptions")
        self.aliases.append("cso")

        self._original_desc = "Interface with the conversation simulator.\n\nArgument 'action' should be either 'get' or 'set'"
        self.desc = self._original_desc

        self.addArgument(Argument("action", CmdTypes.STR))
        self.addArgument(Argument("option", CmdTypes.STR))
        self.addArgument(Argument("value", CmdTypes.STR, True))
        
        self.ownerOnly = True

    async def getHelp(self):
        
        #Update command description to include option hints generated from currently active conversation simulator
        res = chatutils.mdCode(await CONVERSATION_SIMULATOR.getOpt("HELP"))
        self.desc = self._original_desc + "\n\nAvailable options for conversation simulator %s:\n%s" % (CONVERSATION_SIMULATOR.name, res)

        return await super().getHelp()

    async def call(self, action, option, value=None):

        action = action.lower()
        if action == "get":
            self.logger.debug("Getting CS option '%s'..." % option)
            try:
                res = str(await CONVERSATION_SIMULATOR.getOpt(option))
            except NotImplementedError:
                await self.respond("This option is not supported by this implementation.", True)
                return
            await self.respond("Value of '%s': '%s'" % (option, res))

        elif action == "set":
            self.logger.debug("Setting CS option '%s'..." % option)
            try:
                await CONVERSATION_SIMULATOR.setOpt(option, value)
            except NotImplementedError:
                await self.respond("This option is not supported by this implementation.", True)
                return

        else:
            await self.respond("Action must be either 'get' or 'set'.", True)

COMMANDS.append(CmdCSOpt())

class CmdSudo(Command):

    def setup(self):

        self.name = "sudo"
        self.desc = "Gain superuser privileges.\n\nThis command allows you to execute other commands from the console (i.e.: with root access) from anywhere."
        self.hidden = True
        self.ownerOnly = True #only the bot owner should ever be able to gain root access
        self.allowConsole = False #having access to this on the console wouldn't make much sense
        self.addArgument(Argument("cmd", CmdTypes.STR))
        self._cmd = ""

    async def call(self, cmd):

        self._cmd = cmd.encode()
        responseHandle = ResponseManager(reader=self, writer=self)
        await process_command(responseHandle)

    #Standard bytestream interface methods go here

    async def readline(self):

        return self._cmd

    async def read(self):

        return self._cmd

    def write(self, msg):

        asyncio.get_event_loop().create_task(self.respond(msg.decode(), True))

    def close(self):

        pass

COMMANDS.append(CmdSudo())

class CmdTempElevate(Command):

    def setup(self):

        self.name = "elevate"
        self.desc = "Elevate a users permission. This command will add an exception to a users permissions that allows them to bypass any command specific permissions.\nThis effect only lasts until the bot restarts."
        self.hidden = True
        self.ownerOnly = True
        self.addArgument(Argument("action", CmdTypes.STR))
        self.addArgument(Argument("user", CmdTypes.MEMBER))

    async def call(self, action, user):

        if action == "add":
            SUPERUSERS.add(user.id)
            await self.respond("Added user %s to the list of temporary superusers." % user.name)

        elif action == "remove":
            SUPERUSERS.discard(user.id)
            await self.respond("Removed user %s from the list of temporary superusers." % user.name)

        else:
            await self.respond("Error: action must be 'add' or 'remove', not '%s'." % action, True)

COMMANDS.append(CmdTempElevate())

class CmdReloadCommands(Command):

    def setup(self):

        self.name = "reload"
        self.aliases.append("reloadCommands")
        self.aliases.append("reloadCmds")
        self.desc = "Reloads all external commands. Internal commands are part of the core codebase and thus cannot be reloaded while the bot is running."
        self.ownerOnly = True

    async def call(self):

        global COMMANDS
        global internal_commands
        loop = asyncio.get_event_loop()

        await self.respond("Initializing...")
        start = time.time()
        COMMANDS.clear()
        COMMANDS.extend(internal_commands) #first, add back all internal commands

        await self.respond("Reloading commands...")
        external = await loop.run_in_executor(None, loadCommands, "commands")
        COMMANDS.extend(external) #second, reload all external commands and add them back

        await self.respond("Reload completed in %.2f second(s). %i commands loaded (%i internal, %i external)." % (time.time()-start, len(COMMANDS), len(internal_commands), len(external)), True)

COMMANDS.append(CmdReloadCommands())

internal_commands = COMMANDS.copy()

logger = logging.getLogger("Command")
logger.info("Loading external commands...")

external_commands = loadCommands("commands")
int_cmd_c = len(internal_commands)
ext_cmd_c = len(external_commands)
logger.info("%i commands loaded (%i internal, %i external)." % (int_cmd_c+ext_cmd_c, int_cmd_c, ext_cmd_c))
COMMANDS.extend(external_commands) #include external commands

#CONSTANTS

#Auth information (actually only need the token)
CLIENT_ID = CONFIG_MANAGER.getElementText("bot.clientID")
CLIENT_SECRET = CONFIG_MANAGER.getElementText("bot.clientSecret")
AUTH_TOKEN = CONFIG_MANAGER.getElementText("bot.token") # <- important

USERNAME = CONFIG_MANAGER.getElementText("bot.username")
PASSWORD = CONFIG_MANAGER.getElementText("bot.password")

GAME = discord.Game(name="%s | %s%s" % (version.S_VERSION, CMD_PREFIX, "about")) #We can set this later, just so we have something to display

#Voice related things
SOUND_DIR = "sounds/"
SOUNDS_RECORDING = {} #channel: FileRecorder instance

PENDING_REACTION_HANDLES = []

ICONS = { #Discord chat icons
    "ok": CONFIG_MANAGER.getElementText("bot.icons.ok"),
    "forbidden": CONFIG_MANAGER.getElementText("bot.icons.forbidden"),
    "error": CONFIG_MANAGER.getElementText("bot.icons.error"),
    "pin": CONFIG_MANAGER.getElementText("bot.icons.pin")
    }

#PROGRAM FLAGS (THESE CAN BE EDITED)
DEBUG_CONSOLES = True #will force additional terminals to spawn for debug purposes. Should be disabled on release versions. Slightly buggy atm, recommended to be left on
NICKNAME_LOCKED = True #While this is true, any attempts to change the bots nickname will result in it being automatically changed back.
USE_VOICECOM = False #Set this to True to use voice receiving hooks.

#STATE VARIALBES (DON'T EDIT THESE)
NICKNAME_REVERTED = False #Indicates that the bot changed its nickname back and expects the resulting event to be dispached shortly
AUTOSAVE_ACTIVE = False #Indicates if an autosave subroutine is currently running. Used to prevent autosave from triggering more than once per session

#addresses for networking

host = CONFIG_MANAGER.getElementText("bot.network.host.IP", "localhost") #address of this machine (usually localhost, unless you want to access the bot from a different computer)
controlPort = CONFIG_MANAGER.getElementInt("bot.network.host.controlPort", 50010) #port to listen on for remote control interface

client = discord.Client()

#CONVERSATION_SIMULATOR = conversation.MegaHAL(client, CONFIG_MANAGER)
CONVERSATION_SIMULATOR = conversation.BrianCS(client, CONFIG_MANAGER)

#New audio engine
AUDIO_MANAGER = audio.AudioManager(client)

#Load chat interaction scripts
logger = logging.getLogger("CIDSL")
logger.info("Setting up CIDSL interpreter namespace...")
ciparser = interaction.DSLParser()
CIINTERPRETER = interaction.DSLInterpreter(client)
CIINTERPRETER.registerAudioEngine(AUDIO_MANAGER) #make sure we can playback sounds
logger.info("Loading scripts...")
for i in os.listdir("chat/scripts"):
    p = os.path.join("chat/scripts", i)
    if (not os.path.isfile(p)) or (not p.endswith(".ci")):
        continue
    f = open(p, "r")
    logger.debug("Loading CIDSL script at %s..." % p)
    try:
        CIINTERPRETER.compile(ciparser.parse("\n".join(f.readlines())))
    except:
        logger.exception("Exception occured while loading CIDSL script at %s: " % p)
    f.close()

if USE_VOICECOM:
    logger = logging.getLogger("Voicecom")
    logger.info("Initializing Google Cloud Speech interface...")
    VOICEHANDLE = voicecom.VoiceHandle() #init our Google Cloud Speech interface
    logger.info("Installing UDP voice connection hook...")
    CONNECTIONLISTENER = voicecom.ConnectionListener(client) #init our UDP voice packet listener and register interceptor methods. This object should now do everything on its own. We just need to set it some limits every so often

logging.info("Loading done!")
cmdutils.printSeparator()

#COROUTINES

async def console_cb(reader, writer):

    """
    Interface for console input
    """

    responseHandle = ResponseManager(reader=reader, writer=writer)
    try:
        await processCommand(responseHandle, COMMANDS, CONFIG_MANAGER, client, DATABASE_MANAGER, AUDIO_MANAGER) #use our new interface | create ResponseManager
    except:
        #now that we are sending the responses via network to the caller we need to perform some cleanup in case shit goes sideways
        responseHandle.close()
        raise

async def save():

    """
    Save the bot configuration. Will also prompt all subsystems to create a backup of their current state.
    The bot will run this method automatically every 5 minutes.
    """

    #saves CS state
    await CONVERSATION_SIMULATOR.setOpt("SAVE", None)

    #save config (Do this last so save functions of other subsystems can refresh their config information first)
    CONFIG_MANAGER.save()

async def autosave():


    """
    Autosave feature.
    This task will be activated as soon as the client connects.
    Afterwards it will save every 5 minutes until bot termination.
    """

    #Saves the state of various algorithms that depend on config information

    logger = logging.getLogger("Autosave")

    global AUTOSAVE_ACTIVE

    if AUTOSAVE_ACTIVE:
        logger.warn("Autosave was initialized but it is already running")
        return #Autosave routine already running

    while not client.is_closed:
        AUTOSAVE_ACTIVE = True
        await asyncio.sleep(300)
        
        logger.info("Starting backup...")
        await save()
        logger.info("Backup complete!")

    AUTOSAVE_ACTIVE = False

#DISCORD EVENTS

@client.event
async def on_ready():

    #called on bot login after connection. At least it used to be...

    logger = logging.getLogger("Discord")
    logger.info("Client logged in as " + cmdutils.formatText(client.user.name, bold=True) + " (" + client.user.id + ")")
    if client.user.bot:
        logger.info("Client is using a bot account, feature restrictions may apply")

    cmdutils.printSeparator()
    logger.warn("This is a headless server in that it doesn't provide a way to input commands directly into the console. Please use chat commands to control it.")
    cmdutils.printSeparator()

    #start autosave coroutine
    #Apparently Discord changed how the login works, this call throws an error every time because the WebSocket disconnects for some reason. For now, we fix it by adding a slight delay.
    await asyncio.sleep(3) #wait for the bot to connect
    client.loop.create_task(autosave())

    #set playing state
    await client.change_presence(game=GAME)

@client.event
async def on_message(msg):

    #Handle incoming messages

    logMessage(msg)

    if msg.content.startswith(CMD_PREFIX) and not msg.author.id == client.user.id: #command detected | We don't want the bot to be able to input commands
        
        await processCommand(ResponseManager(client=client, msg=msg), COMMANDS, CONFIG_MANAGER, client, DATABASE_MANAGER, AUDIO_MANAGER)

    #Crashes Wacky Emoji Copy Pasta Warehouse And Emporium
    #elif msg.author.id == "125311707919679488":

    #    ratio = 2
    #    symbols = msg.content.split(" ") #split string into space separated symbols
    #    words = []
    #    nonwords = []
    #    for i in symbols:
    #        if i.isalnum():
    #            words.append(i)
    #        else:
    #            nonwords.append(i)
    #    if len(nonwords) and len(words)/len(nonwords) < ratio: #Too many emojis
    #        await client.send_message(msg.channel,msg.author.mention+", Did you mean '"+" ".join(words)+"' ?")
    #        return

    else:
        if client.user.mentioned_in(msg) and not msg.author.id == client.user.id:

            await client.send_typing(msg.channel) #makes it seem more real (TODO: we need a way to terminate this if the following code throws an error)

            #SPECIAL CASES (Easter eggs)

            if CIINTERPRETER.run(msg):
                return

            #Initiate self destruct sequence, authorization code: *******************
            elif chatutils.checkForWords(["initiate", "self", "destruct", "sequence"], msg.content):
                await client.send_message(msg.channel,msg.author.mention + ", Access denied: Authentification required. 30 seconds until lockout.")
                auth_code = await client.wait_for_message(timeout=30, author=msg.author, channel=msg.channel)
                if not auth_code:
                    return
                elif auth_code.content == "LucioLover69": #:P
                    await client.send_message(msg.channel, msg.author.mention + ", Affirmative. Self destruct command received. Initializing...")
                    await asyncio.sleep(3)
                    await client.send_message(msg.channel, "Self destruct sequence successfully initialized. 60 seconds until detonation.")
                    await asyncio.sleep(30)
                    await client.send_message(msg.channel, "30 seconds until detonation.")
                    await asyncio.sleep(20)
                    await client.send_message(msg.channel, "10 seconds until detonation.")
                    await asyncio.sleep(5)
                    for i in range(5,0,-1):
                        await client.send_message(msg.channel, str(i))
                        await asyncio.sleep(1)
                    await asyncio.sleep(6)
                    await asyncio.send_message(msg.channel, "Code 5011, internal socket error. Self destruct command could not be executed correctly. Access violation at Address 0xFFFFFFyF88FF.//ok*}|^lll'lr__422&+erROr:;<<<<<<<<")
                    return
                else:
                    await client.send_message(msg.channel, msg.author.mention + ", Access denied.")
                    return

            #use our MegaHal implementation to get a response

            if CONFIG_MANAGER.getElementText("bot.chat.aistate") == "off": #AI turned off
                await client.send_message(msg.channel, msg.author.mention + ", Sorry, this feature is unavailable right now. Please try again later.")
                return

            if msg.server:
                #Check if this channel is blocked for AI
                db = DATABASE_MANAGER.getServer(msg.server.id)
                ds = db.createDatasetIfNotExists("blockedChannels", {"channelID": msg.channel.id})
                if ds.exists(): #YOU'RE BANNED
                    await client.send_message(msg.channel, msg.author.mention + ", " + interaction.confused.getRandom())
                    return

            if not ("<@" + client.user.id + ">" in msg.content or "<@!" + client.user.id + ">" in msg.content): #cheking for group mentions
                #must be either @here or @everyone... make this a rare occurance
                if random.random() > 0.01: #only process every 100th message
                    return


            response = await CONVERSATION_SIMULATOR.respond(msg)

            if CONFIG_MANAGER.getElementText("bot.chat.aistate") == "passive": #AI in passive mode
                return

            if isinstance(response, bytes):
                await client.send_message(msg.channel, msg.author.mention + ", " + response.decode()) #post our answer
            else:
                await client.send_message(msg.channel, msg.author.mention + ", " + response)

        elif len(msg.content) > 0 and (not msg.author.id == client.user.id): #we don't want the bot to listen to its own messages

            if "Remember that everything posted in here is absolute dogshit." in msg.content and msg.author.id == "159985870458322944":
                await client.send_message(msg.channel, msg.author.mention + ", you're absolute dogshit.")
                await asyncio.sleep(60)
                await client.delete_message(msg)

            elif (msg.content.lower().endswith(", you're absolute dogshit.") or msg.content.lower().endswith(", watch your language!!! :rage:")) and msg.author.id == client.user.id:
                await asyncio.sleep(120)
                await client.delete_message(msg)

            elif "#votepy" in msg.content.lower():
                await client.delete_message(msg)
                await client.send_message(msg.channel, msg.author.mention + ", WATCH YOUR LANGUAGE!!! :rage:")

            pp = interaction.calculatePrivilegePoints(msg.content)
            if pp >= 1:
                #add pp to user using our database implementation
                dbHandle = DATABASE_MANAGER.getServer(msg.server.id)
                dbHandle.createTableIfNotExists("privilegePoints", {"user": "text", "points": "int"}, True)
                ds = dbHandle.createDatasetIfNotExists("privilegePoints", {"user": msg.author.id}) #get the users pp entry or create one

                ds.setValue("points", ds.getValue("points") + pp) #Add our privilege points to the total count

                ds.update() #update the dataset

                #deactivated this, it's better this way

                #await client.send_message(msg.channel, msg.author.mention+", congratulations, you were just awarded "+str(pp)+" :pp:")

            #We are using Google Assistant now so we don't want to feed it data unless we absolutely mean to
            #return

            #Teach our AI
            if not msg.content.startswith("#") and not msg.content.startswith("+") and not msg.content.startswith("-") and not msg.content.startswith(":musical_note:"): #We don't want the user to be able to enter commands through the chat interface

                if CONFIG_MANAGER.getElementText("bot.chat.aistate") == "off": #AI turned off
                    return

                if msg.server:
                    #Check if this channel is blocked for AI
                    db = DATABASE_MANAGER.getServer(msg.server.id)
                    ds = db.createDatasetIfNotExists("blockedChannels", {"channelID": msg.channel.id})
                    if ds.exists(): #YOU'RE BANNED
                        return

                await CONVERSATION_SIMULATOR.observe(msg)

            c = msg.content.lower()
            if " ram " in c or c.startswith("ram ") or c.endswith(" ram") or c == "ram": #Make the bot sometimes respond to its name when it comes up

                for i in msg.server.emojis: #Always try to add a "Ram" emoji if available
                    if i.name.lower() == "ram":
                        await client.add_reaction(msg, i)
                        break

                if random.random() <= 0.001: #Responds with a probability of 1:1000
                    await client.send_message(msg.channel, interaction.mentioned.getRandom()) #IT HAS BECOME SELF AWARE!!!


@client.event
async def on_voice_state_update(before,after):

    #Voice line handling
    if (after.voice_channel and after.voice_channel != before.voice_channel): #if the user is connected and has changed his voice channel (this may mean he just joined)
        if after.server.voice_client and (after.voice_channel == after.server.voice_client.channel): #we are in the same channel as our target

            #Use new dynamic voiceline handling (voicelines are compared by User ID / Filename instead of a dictionary lookup
            #This isn't necessarily any faster but it is more convenient and doesn't require a restart to assign voicelines
            dir = os.listdir(SOUND_DIR + "voicelines")
            for i in dir:
                if os.path.isdir(SOUND_DIR + "voicelines/" + i) and  i == after.id: #we have a voiceline folder for this member
                    files = os.listdir(SOUND_DIR+"voicelines/" + i)
                    if not files: #no voicelines found, return
                        return
                    filepath = SOUND_DIR+"voicelines/" + i + "/"+random.choice(files)
                    sound = audio.FFMPEGSound(filepath)
                    AUDIO_MANAGER.playSound(sound, after.voice_channel, sync=False)
                    return

@client.event
async def on_resumed():

    logger = logging.getLogger("Discord")
    logger.info("Client lost connection but successfully recovered.")

@client.event
async def on_reaction_add(reaction, user):

    #upvote :Ram: emoji if someone added it to a message
    if isinstance(reaction.emoji, discord.Emoji):
        name = reaction.emoji.name
    else:
        name = reaction.emoji
    if name.lower() == "ram" and not reaction.me: #This should work for either "ram", "Ram", ":ram:" or ":Ram:"
        await client.add_reaction(reaction.message, reaction.emoji)

@client.event
async def on_member_update(before, after):

    logger = logging.getLogger("Discord")
    #Nickname protection
    if after.id == client.user.id: #this is the bot
        if before.nick != after.nick: #the nickname changed
            if NICKNAME_LOCKED:
                if NICKNAME_REVERTED:
                    NICKNAME_REVERTED = False
                    return
                try:
                    await client.change_nickname(after, before.nick) #revert nickname changes
                    NICKNAME_REVERTED = True
                    logger.info("Successfully intercepted nickname change!")
                except:
                    #permissions are missing
                    logger.error("Failed to auto change nickname!")

@client.event
async def on_call(call, *args, **kwargs):

    """
    Undocumented call handler coroutine method.
    Since I have very little info about its signature I'll put the args/kwargs there to prevent crashes.
    Only known positional argument atm is the GroupCall instance.
    """

    logger = logging.getLogger("DM Call")
    logger.info("Receiving call from channel " + (call.channel.name if call.channel.name else call.channel.user.name) + ", attempting to join...")

    if len(call.connected) < 1:
        logger.error("No one in call, cannot join")
        return

    voiceState = call.voice_state_for(call.connected[0])
    if not voiceState:
        logger.error("Unable to determine voice channel for call")
        return

    try:
        await client.join_voice_channel(voiceState.voice_channel)
    except discord.InvalidArgument:
        logger.exception("Failed to join call: Call channel is not a voice channel.")
    except asyncio.TimeoutError:
        await client.send_message(call.channel, "Unable to connect to call right now. Please try again.")
    except discord.ClientException:
        pass
    except discord.opus.OpusNotLoaded:
        logger.error("Call could not be initialized due to opus library being uninitialized.")

#Set up RAT response server

logging.info("Starting command server...")
coro = asyncio.start_server(console_cb, host, controlPort, loop=client.loop) #we also need to listen for incoming commands on the console.
client.loop.run_until_complete(coro)
logging.info("RPC port open, listening on %s:%i" % (host, controlPort))

#MAIN LOOP

logger = logging.getLogger("Discord")
logger.info("Attempting to log in...")
try:
    while True:
        #For some reason, sometimes this call returns despite the server still running.
        #Since we have no idea what exactly happens in these cases, we will attempt to relog
        #if the call returns OR SystemExit is raised.
        #We usually close the bot by executing the quit command, any other way of termination should either
        #lead to a crash (in situations where recovery is impossible) or automatically restart the discord client.
        try:
            if AUTH_TOKEN:
                client.run(AUTH_TOKEN)
            elif USERNAME and PASSWORD:
                client.run(USERNAME, PASSWORD)
            else:
                raise ValueError("Must either specify bot token or user account credentials.")
        except SystemExit:
            #This shouldn't happen, we close the event loop to signal process termination
            logger.warn("SystemExit was raised in client.run(), relogging...")
            continue
        if client.loop.is_closed():
            #If the discord client actually closes the loop this may be an issue,
            #in that case we'd need to keep track of the state of the application
            #using a global variable
            break
        logger.warn("Discord client connection terminated (Reason: Unknown), relogging...")

#Everything not caught by the code in the while loop above is considered a critical error,
#which means recovery is most likely impossible and will not be attempted.
#In any case, the bot should attempt to shut down orderly to prevent data corruption and desync.
#Error handles may provide additional information on the issue that occured.

except discord.LoginFailure as e: #for some reason we crashed. We'll just exit
    logger.exception("During login the following exception occured")
    logging.info("\nShutting down...")

    sys.exit(1)

except Exception as e:

    #catch exceptions, mainly WebSocket errors. We want the program to shut down properly so all cleanup functions get executed (and everything is saved)
    logger.critical("Main loop crashed due to fatal error: " + str(e))
    logger.exception("Exception occured")
    logging.info("Shutting down...")

    sys.exit(1) #run cleanup functions, then exit (reboot will be handled by RAT if present)

sys.exit(0)