from typing import Callable
import importlib
import logging
import os
import traceback

from discord import Message, TextChannel, User, Emoji

import interaction

from ._globals import CLEANUP_FUNCTIONS, SUPERUSERS
from .abcs import Command

logger = logging.getLogger("cmdsys.utils")

def cleanUpRegister(func: Callable, *args, **kwargs):

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

async def dialogConfirm(msg: Message, client: "ProtosBot") -> bool:

    """
    Ask the user to confirm an action.
    """

    await msg.channel.send(msg.author.mention+", "+interaction.confirm.getRandom())
    response = await client.wait_for_message(timeout=30, author=msg.author, channel=msg.channel)
    if not response: #message timed out, user took too long or didn't respond at all
        return False
    if response.content.lower() in ["yes","yup","yee","ya","yas","yaaas","yeah","yea"]: #extend these if needed
        return True
    return False

async def dialogReact(channel: TextChannel, user: User, client: "ProtosBot", message: Message=None, emoji: Emoji=None, timeout=30) -> Message:

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

def load_commands(path):

    """
    Load commands from a directory.
    """

    logger = logging.getLogger("cmdsys.utils.loader")
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
                        raise
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