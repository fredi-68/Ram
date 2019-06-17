#Discord ProtOS Bot
#
#Author: fredi_68
#
#Coversation simulator interfaces

import asyncio
import logging
import functools as ft

from brianCS import BrianModel
from brianCS.enums import *
HAS_GASSIST = True
try: #GAssist package is optional
    import gassist #urgh...
except:
    HAS_GASSIST = False

class ConversationSimulator():

    """
    Abstract base class for conversation simulators.

    This class serves as an interface standard for conversation simulator plugins.
    To implement a conversation simulation algorithm, override the coroutines
    observe() and respond(). Refer to method signatures for more information.

    Because observe() and respond() are implemented as coroutines, they should
    not include direct calls to long running subroutines. It is advised to either
    connect to a conversation simulator through a networking interface or running
    the respective calls responsible for communication in some sort of threadpool.

    The setOpt() and getOpt() configuration interface may be used to provide the user
    with a means of interacting with the conversation simulator directly. There is no
    standardized set of options that are recognized; instead, each implementation
    defines its own set of options. If the user requests an option that does not
    exist, NotImplementedError should be raised so that the options interface can correctly
    handle the error.
    Despite there not being a standardized set of options, there are some options
    that - if available - will be used by the bot to manage the simulator during
    runtime. These options include:

    SAVE (): Set only. Store the current state of the conversation simulator. If the
        model is stateless, implementing this option does not make much sense.
        By default, SAVE is called in regular intervals, if a backup is requested by
        the user and when the bot is shut down.
    LOAD [path]: Set only. Load a backup state. If this option is set with an argument,
        the conversation simulator is expected to load a backup with the
        provided name. Otherwise one should just reload the current state from
        storage (i.e. revert to model state after last SAVE).
    HELP (): Get only. Should return a string providing information on the supported
        options and their meaning, if applicable. This option will be used by the
        getOpt/setOpt chat interface to prefetch command help pages. These will be
        available through the standard command getHelp feature. Note that even if this
        option is not implemented, the option interface is still available.

    This is an abstract class and should not be instanciated directly.
    """

    logger = logging.getLogger("ConversationSimulator")
    name = "GenericConversationSimulator"

    def __init__(self, client, config):

        """
        Create a new ConversationSimulator instance.

        config is a config.ConfigManager instance. It is provided in case your
        implementation has configurable options, which then can be read from the
        main bot configuration file.
        """

        self.client = client
        self.config = config

    async def observe(self, msg):

        """
        Observe a message typed by a user in chat.

        The returned value of this method is ignored. It is used simply to provide
        the conversation simulator with information about the context of the current
        conversation and also to speed up the training process for systems that are
        trained purely on chat activity. You are not required to implement this
        method but you are highly encouraged to do so.
        """

        pass

    async def respond(self, msg):

        """
        Respond to a message.

        The returned value of this method should be the response to the provided message
        as a string.
        """

        return ""

    async def setOpt(self, key, value):

        """
        Set an option. Support for options is implementation dependend.
        """

        raise NotImplementedError("Unsupported option %s" % key)

    async def getOpt(self, key):

        """
        Get an option. Support for options is implementation dependend.
        """

        raise NotImplementedError("Unsupported option %s" % key)

class MegaHAL(ConversationSimulator):

    """
    MegaHAL conversation simulator wrapper.

    This CS uses MegaHAL, an old markov chain based application,
    running inside a wrapper script accessible over the network.
    To use it, you must have bot.network.AI.IP and bot.network.AI.port
    defined in your main config file. The CS will use this information
    when connecting to the remote MegaHAL instance. This wrapper
    supports standard MegaHAL commands and exposes them through the
    setOpt/getOpt interface.
    """

    COMMANDS = [
        "QUIT",
        "EXIT",
        "SAVE",
        "SPEECH",
        "DELAY",
        "VOICES",
        "VOICE",
        "BRAIN",
        "HELP"
        ]

    name = "MegaHAL"

    def __init__(self, client, config):

        super().__init__(client, config)
        self.ip = config.getElementText("bot.network.AI.IP", "localhost")
        self.port = config.getElementInt("bot.network.AI.port", 50011)

    def _prepareMessage(self, msg):

        """
        Prepares a chat message for export to the AI process via local IPv4 loopback
        """

        s = msg.content.replace("<@" + self.client.user.id + ">", "") #make sure the bot mention doesn't show up if it was input
        s = s.replace("<@!" + self.client.user.id + ">", "") #secondary mention format
        s = s.lstrip(" ,") #Do this last so there aren't any unnecessary spaces left

        #command blacklisting
        for i in self.COMMANDS:
            s = s.replace("#" + i, "")

        while s.find("\n\n") >= 0:
            s = s.replace("\n\n", "\n") #Injection protection. Not an ACE or anything but it was causing trouble with linefeeds and also allowed users to insert AI commands directly into the subprocess by using modified messages.
            
        if not s: #we deleted everything... WELL
            return None
        if not (s[-1] in ["?", "!", "."]): #this checks if the sentence was properly terminated
            s += "." #add a period to tell the AI that the sentence ends here, otherwise it will fuck up mentions and emotes
        return s.encode() #prepare message for network transfer

    async def _communicate(self, text, wait):

        """
        Helper function for communicating with the AI
        """

        try:
            reader, writer = await asyncio.open_connection(self.ip, self.port, loop=self.client.loop) #open connection to the AI
        except:
            self.logger.exception("Error while trying to connect to AI server: ")
            return "Error: Connection to AI server could not be established."
    
        try:
            writer.write(text)
            if writer.can_write_eof():
                writer.write_eof()
        except:
            self.logger.exception("An error occured while communicating with AI process: ")
            return "Error: Communication with host process failed."

        if wait:
            try:
                result = await reader.read(-1)
                writer.close()
            except:
                self.logger.exception("An error occured while retrieving the result: ")
                return "Error: No response from host process."
            return result.decode()
    
        try:
            writer.close()
        except:
            pass
        return ""

    async def observe(self, msg):

        text = self._prepareMessage(msg)
        await self._communicate(text, False)

    async def respond(self, msg):
        
        text = self._prepareMessage(msg)
        return await self._communicate(text, True)

    async def setOpt(self, key, value):

        """
        Execute MegaHAL commands on the remote AI server.
        key should be one of the supported MegaHAL commands,
        see MegaHAL.COMMANDS for reference.
        value may either be a string or integer, or a list of strings.
        Use it to specify additional arguments for the command.
        Note: Not all commands accept additional arguments, refer to the MegaHAL
        documentation for more information.
        """

        if not key in self.COMMANDS:
            raise NotImplementedError("Unsupported option %s" % key)

        args = []
        if isinstance(value, str):
            args.append(value)
        elif isinstance(value, int):
            args.append(str(value))
        elif isinstance(value, (list, tuple, set)):
            args.extend(value)
        argstr = " ".join(args)
        cmd = "#%s %s" % (key, argstr)
        self.logger.debug("Executing MegaHAL command '%s'" % cmd)
        await self._communicate(cmd.encode(), False)

    async def getOpt(self, key):

        if key == "HELP":
            return ", ".join(self.COMMANDS)
        raise NotImplementedError("Unsupported option %s" % key)

class GoogleAssistant(ConversationSimulator):

    """
    Google Assistant CS.

    This CS uses the Google Assistant API to get text responses.

    A Google Developer account with Google Assistant API access is
    required to use this wrapper interface.
    Refer to gassist.py for more information.
    """

    name = "Google Assistant"

    def __init__(self, client, config):

        super().__init__(client, config)
        if not HAS_GASSIST:
            raise RuntimeError("gassist module unavailable")
        self._googleAssistant = gassist.GoogleAssistant(self.config)

    async def respond(self, msg):
        
        res = await self.client.loop.run_in_executor(None, self._googleAssistant.getTextResponse, (msg.context,))

        return res

class BrianCS(ConversationSimulator):

    """
    BrianCS

    This CS was developed specifically for the ProtOS Discord Bot.
    It utilizes all the features provided by the conversation interface.
    More information on the model and its functionality can be found
    at BrianCS/model.py

    This CS runs inside the main application. By default, it does not
    provide a networking interface or multi core processing options.
    It is threaded however.
    """

    name = "Brian CS"
    MODEL_PATH = "brianCS/model.zip"

    def __init__(self, client, config):

        super().__init__(client, config)
        self.model = BrianModel() #TODO: Add model configuration from config file for new models
        self.model.load(self.MODEL_PATH)

        def positive(x):

            x = int(x)
            if x < 0:
                raise RuntimeError("Must be greater or equal to 0")
            return x

        def positive_nz(x):

            x = int(x)
            if x < 1:
                raise RuntimeError("Must be greater or equal to 1")
            return x

        def positive_float(x):

            x = float(x)
            if x < 0:
                raise RuntimeError("Must be greater or equal to 0")
            return x

        def enum_name(enum, x):

            return enum._member_map_[x]

        def not_implemented(x=None):

            raise NotImplementedError("This option does not support this operation.")

        self.options = {
            "SAVE": [not_implemented, self.save, str],
            "LOAD": [not_implemented, self.load, str],
            "blacklist_load": [not_implemented, self.model.loadBlacklist, str],
            "blacklist_add": [not_implemented, self.addToBlacklist, str],
            "blacklist_remove": [not_implemented, self.removeFromBlacklist, str],
            "model_order": [self.getModelOrder, self.setModelOrder, positive_nz],
            "context_bias": [self.getContextBias, self.setContextBias, positive_float],
            "dropout_chance": [self.getDropoutChance, self.setDropoutChance, positive_float],
            "max_predictions": [self.getMaxPredictions, self.setMaxPredictions, positive_nz],
            "prediction_time": [self.getPredictionTime, self.setPredictionTime, positive_float],
            "dropout_factor": [self.getDropoutFactor, self.setDropoutFactor, positive_float],
            "dropout": [self.getDropout, self.setDropout, ft.partial(enum_name, Dropout)],
            "dropout_curve": [self.getDropoutCurve, self.setDropoutCurve, ft.partial(enum_name, DropoutCurve)]
            }

    def addToBlacklist(self, name):
        if not name in self.model.blacklist:
            self.model.blacklist.append(name)

    def removeFromBlacklist(self, name):
        if name in self.model.blacklist:
            self.model.blacklist.remove(name)

    def getModelOrder(self):
        return self.model.modelOrder

    def setModelOrder(self, ord):
        self.model.genForward.order = ord
        self.model.genBackward.order = ord
        self.model.modelOrder = ord

    def getContextBias(self):
        return self.model.context_bias

    def setContextBias(self, bias):
        self.model.context_bias = bias

    def getDropoutChance(self):
        return self.model.dropout_chance

    def setDropoutChance(self, chance):
        self.model.dropout_chance = chance

    def getMaxPredictions(self):
        return self.model.max_predictions

    def setMaxPredictions(self, m):
        self.model.max_predictions = m

    def getPredictionTime(self):
        return self.model.prediction_time

    def setPredictionTime(self, t):
        self.model.prediction_time = t

    def getDropoutFactor(self):
        return self.model.dropout_factor

    def setDropoutFactor(self, t):
        self.model.dropout_factor = t

    def getDropout(self):
        return self.model.dropout

    def setDropout(self, t):
        self.model.dropout = t

    def getDropoutCurve(self):
        return self.model.dropout_curve

    def setDropoutCurve(self, t):
        self.model.dropout_curve = t

    def load(self, path=None):

        if not path:
            path = self.MODEL_PATH
        self.model.load(path)

    def save(self, path=None):

        if not path:
            path = self.MODEL_PATH
        self.model.save(path)

    def _prepareMessage(self, msg):

        """
        Prepares a chat message for export to the AI process via local IPv4 loopback
        """

        s = msg.content.replace("<@" + str(self.client.user.id) + ">", "") #make sure the bot mention doesn't show up if it was input
        s = s.replace("<@!" + str(self.client.user.id) + ">", "") #secondary mention format
        s = s.lstrip(" ,") #Do this last so there aren't any unnecessary spaces left

        if not s: #we deleted everything... WELL
            return None
        return s #prepare message for network transfer

    async def observe(self, msg):

        t = self._prepareMessage(msg)
        await self.client.loop.run_in_executor(None, self.model.observe, t.lower(), msg.channel.name)

    async def respond(self, msg):
        
        t = self._prepareMessage(msg)
        res = await self.client.loop.run_in_executor(None, self.model.respond, t.lower(), msg.channel.name)

        return res

    async def getOpt(self, key):
        
        if key == "HELP":
            opts = ["HELP"]
            opts.extend(self.options.keys())
            return ", ".join(opts)
        elif key in self.options:
            return self.options[key][0]()
        else:
            raise NotImplementedError("Unsupported option %s" % key)

    async def setOpt(self, key, value):

        if key == "SAVE":
            self.save(value)
        elif key == "LOAD":
            self.load(value)
        elif key in self.options:
            get, set, t = self.options[key]
            value = t(value)
            set(value)

        else:
            raise NotImplementedError("Unsupported option %s" % key)
