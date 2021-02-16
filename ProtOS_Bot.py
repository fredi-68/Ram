import logging
import os
import json
import asyncio
import random
import sys
from pathlib import Path

import discord
from discord import Client, Message, Game

from config import ConfigManager, DatabaseManager
import cmdutils
import cmdsys
from response_manager import ChatResponse
from audio import AudioManager, FFMPEGSound
from version import S_TITLE_VERSION, S_VERSION
from conversation import BrianCS
import interaction
from voicecom import ConnectionListener
from voicecom import RhasspyRE

from core_models import *

interaction.init()

class ProtosBot(Client):

    """
    ProtOS Discord Bot
    """

    logger = logging.getLogger("Bot")

    CMD_PATH = Path("commands")
    CFG_PATH = Path("config")
    SOUND_DIR = Path("sounds")

    def __init__(self, token=None, cs=BrianCS, use_voice_receive_hooks=False):

        """
        Create a new bot instance.

        token is the bot token to authenticate with.
            If it is None, the token will be read from the configuration file instead.
        cs is the class of the conversation simulator to use. It must be a subclass of
            conversation.ConversationSimulator(). Defaults to conversation.BrianCS().
        """

        super().__init__()

        self._autosave_active = False

        self.event(self.on_message)
        self.event(self.on_ready)

        self.command_parser = cmdsys.CommandParser()
        self.config = ConfigManager(path=self.CFG_PATH / "bot.xml", requireVersion=2)
        self.db = DatabaseManager(path=self.CFG_PATH / "db")
        self.audio = AudioManager(self)
        self.cs = cs(self, self.config)
        self.voice_receive =  None
        if use_voice_receive_hooks:
            rhasspy_address = (self.config.getElementText("bot.network.rhasspy.host"), self.config.getElementInt("bot.network.rhasspy.port"))
            self.voice_receive = ConnectionListener(self, RhasspyRE(rhasspy_address))
            self.logger.warn("Voice receive hooks have been ENABLED. This is considered an experimental feature and should be used with great caution.")

        self.cidsl_parser = interaction.DSLParser()
        self.cidsl = interaction.DSLInterpreter(self)
        self.cidsl.registerAudioEngine(self.audio)
        for i in os.listdir("chat/scripts"):
            p = os.path.join("chat/scripts", i)
            if (not os.path.isfile(p)) or (not p.endswith(".ci")):
                continue
            f = open(p, "r")
            self.logger.debug("Loading CIDSL script at %s..." % p)
            try:
                self.cidsl.compile(self.cidsl_parser.parse("\n".join(f.readlines())))
            except:
                self.logger.exception("Exception occured while loading CIDSL script at %s: " % p)
            f.close()

        cmdsys.environment.update_environment({
            "client": self,
            "config": self.config,
            "database": self.db,
            "audio": self.audio,
            "conversation_simulator": self.cs,
            "voice_receive": self.voice_receive,
            "cidsl": self.cidsl
            })

        self.load_commands()

        self.token = token or self.config.getElementText("bot.token")

    def load_commands(self):

        """
        (Re)loads commands.
        """

        self.commands = cmdsys.load_commands(self.CMD_PATH)
        for command in self.commands:
            command.client = self

    def run(self):

        """
        Run the bot instance. This call will block.
        """

        self.logger.debug("Starting...")
        super().run(self.token)

    def log_message(self, msg: Message):

        """
        Logs the message to the console window.
        Includes pretty printer options for server, channel, names/nicknames and role color
        """
        
        logger = self.logger.getChild("MessageLog")

        s = cmdutils.translateString(msg.content)
        a = cmdutils.translateString(msg.author.name)
        if hasattr(msg.author, "nick") and msg.author.nick:
            a = cmdutils.translateString(msg.author.nick) + "/" + a
            
        for i in msg.attachments: #display attachments
            s += "\n    => with attachment:"
            for j in i.items():
                s += "\n       " + j[0] + ": " + str(j[1])

        if isinstance(msg.channel, discord.abc.PrivateChannel): #We received a DM instead of a server message, this means most of our code is not required
            if isinstance(msg.channel, discord.DMChannel):    
                name = msg.channel.recipient.name
            else:
                name = getattr(msg.channel, "name", msg.channel.recipients[0].name)
            
            logger.info("[DM][%s](%s): %s" % (name, a, s))
            return

        color = msg.author.colour.to_rgb() if hasattr(msg.author, "colour") else (0, 0, 0)
        logger.info("[%s][%s](%s): %s" % (msg.guild.name, msg.channel.name, cmdutils.colorText(a, color), s))

    async def on_ready(self):

        """
        Event handler for ready events.

        Finishes initialization and schedules periodic tasks.
        """

        self.logger.info(S_TITLE_VERSION)
        self.logger.info("-"*50)
        self.logger.info("Ready.")

        await asyncio.sleep(3) #wait a short amount of time until we have received all data
        
        self.logger.debug("Starting autosave scheduler...")
        self.loop.create_task(self._autosave())

        game = Game(name= "%s | %s%s" % (S_VERSION, self.config.getElementText("bot.prefix"), "about"))
        await self.change_presence(activity=game)

    async def on_message(self, msg: Message):

        """
        Event handler for messages.

        Handles command dispatch through text chat as well as interaction with CIDSL and conversation simulators.
        """

        self.log_message(msg)

        if msg.content.startswith(self.config.getElementText("bot.prefix")):
            responseHandle = ChatResponse(self, msg)
            await self.command_parser.parse_command(responseHandle, self.commands, self)

        else:

            if self.user.mentioned_in(msg) and not msg.author.id == self.user.id:

                await msg.channel.trigger_typing() #makes it seem more real (TODO: we need a way to terminate this if the following code throws an error)

                if self.cidsl.run(msg):
                    return

                #use our MegaHal implementation to get a response

                if self.config.getElementText("bot.chat.aistate") == "off": #AI turned off
                    await msg.channel.send(msg.author.mention + ", Sorry, this feature is unavailable right now. Please try again later.")
                    return

                if msg.guild:
                    #Check if this channel is blocked for AI
                    db = self.db.getServer(msg.guild.id)
                    ds = db.createDatasetIfNotExists("blockedChannels", {"channelID": msg.channel.id})
                    if ds.exists(): #YOU'RE BANNED
                        await msg.channel.send(msg.author.mention + ", " + interaction.confused.getRandom())
                        return

                if not ("<@" + str(self.user.id) + ">" in msg.content or "<@!" + str(self.user.id) + ">" in msg.content): #cheking for group mentions
                    #must be either @here or @everyone... make this a rare occurance
                    if random.random() > 0.01: #only process every 100th message
                        return


                response = await self.cs.respond(msg)

                if self.config.getElementText("bot.chat.aistate") == "passive": #AI in passive mode
                    return

                if isinstance(response, bytes):
                    await msg.channel.send(msg.author.mention + ", " + response.decode()) #post our answer
                else:
                    await msg.channel.send(msg.author.mention + ", " + response)

            elif len(msg.content) > 0 and (not msg.author.id == self.user.id): #we don't want the bot to listen to its own messages

                if self.config.getElementText("bot.chat.aistate") == "off": #AI turned off
                    return

                if msg.guild:
                    #Check if this channel is blocked for AI
                    db = self.db.getServer(msg.guild.id)
                    ds = db.createDatasetIfNotExists("blockedChannels", {"channelID": msg.channel.id})
                    if ds.exists(): #YOU'RE BANNED
                        return

                await self.cs.observe(msg)

                c = msg.content.lower()
                if " ram " in c or c.startswith("ram ") or c.endswith(" ram") or c == "ram": #Make the bot sometimes respond to its name when it comes up

                    for i in msg.guild.emojis: #Always try to add a "Ram" emoji if available
                        if i.name.lower() == "ram":
                            await msg.add_reaction(i)
                            break

                    if random.random() <= 0.001: #Responds with a probability of 1:1000
                        await msg.channel.send(interaction.mentioned.getRandom()) #IT HAS BECOME SELF AWARE!!!

    async def on_voice_state_update(self, what, before, after):

        before_channel = before.channel
        after_channel = after.channel

        #Voice line handling
        if (after_channel and after_channel != before_channel): #if the user is connected and has changed his voice channel (this may mean he just joined)
            if what.guild.voice_client and (after_channel == what.guild.voice_client.channel): #we are in the same channel as our target

                #Use new dynamic voiceline handling (voicelines are compared by User ID / Filename instead of a dictionary lookup
                #This isn't necessarily any faster but it is more convenient and doesn't require a restart to assign voicelines
                dir = os.listdir(self.SOUND_DIR / "voicelines")
                for i in dir:
                    if os.path.isdir(self.SOUND_DIR / "voicelines" / i) and  i == str(what.id): #we have a voiceline folder for this member
                        files = os.listdir(self.SOUND_DIR / "voicelines" / i)
                        if not files: #no voicelines found, return
                            return
                        filepath = self.SOUND_DIR / "voicelines" / i / random.choice(files)
                        sound = FFMPEGSound(filepath.as_posix())
                        self.audio.playSound(sound, after_channel, sync=False)
                        return

    async def _autosave(self):

        """
        Periodic autosave task.
        Runs every 5 minutes and writes changes made to the config and the CS to the filesystem.
        """

        logger = self.logger.getChild("Autosave")

        if self._autosave_active:
            logger.warn("Autosave task was triggered but is already running!")
            return

        self._autosave_active = True

        while not self.is_closed():
            await asyncio.sleep(300)

            logger.info("Periodic backup task triggered.")
            await self.save()

        self._autosave_active = False

    async def save(self):

        """
        Save the current configuration.
        """

        self.logger.debug("Saving data...")
        self.config.save()
        await self.cs.setOpt("SAVE", None)
        self.logger.debug("Backup complete!")

    async def shutdown(self, reason=""):

        """
        Shut down the bot.
        This coroutine will correctly deinitialize all submodules and run all cleanup functions
        before shutting down the event loop and exiting.

        reason specifies an optional string to log when shutting the bot down.
        """

        self.logger.info("Shutting down with reason: %s" % reason)

        await cmdsys.cleanUp()

        await self.save()
        await self.logout()
        await self.close()

if __name__ == "__main__":

    #set up logging
    try:
        import fixLogging
    except ImportError:
        pass

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
                    "level": "WARN",
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

    if "--docker" in sys.argv:
        bot = ProtosBot(os.environ.get("BOT_AUTH_TOKEN"))
    else:
        bot = ProtosBot()

    bot.run()