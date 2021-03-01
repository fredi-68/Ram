import logging
import os
import os.path
import importlib
import traceback

from .abcs import Command
from .model_commands import _ModelCommand

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
                if issubclass(thing, Command) and not thing == Command and not issubclass(thing, _ModelCommand):
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