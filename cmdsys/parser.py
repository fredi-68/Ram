from typing import List, Iterable
import logging
import traceback
import shlex

import discord

import interaction
import chatutils

from .abcs import Command, Argument
from ._globals import SUPERUSERS
from .errors import *
from .utils import dialogReact

class CommandParser():

    HELP_COMMAND_ALIASES = ("help", "h", "?")

    logger = logging.getLogger("cmdsys.CommandParser")

    def __init__(self):

        pass

    async def get_help(self, arguments: Iterable[str], command_list: Iterable[Command], response_handle: "ResponseManager") -> bool:

        if not arguments:
            return False
        for command in command_list:
            if arguments[0] in command.names:
                #do we have more arguments (for subcommands)?
                if await self.get_help(arguments[1:], command.subcommands, response_handle):
                    return True
                #help requested for this command
                command._setVariables(response_handle)
                await response_handle.reply(await command.getHelp())
                return True
        return False

    async def print_command_list(self, command_list: Iterable[Command], response_handle: "ResponseManager"):

        await response_handle.reply("Available commands:\n\n" + "\n".join([i.getUsage() for i in command_list]))

    async def _parse_command(self, response_handle, command_string, arguments, command_list, client):

        """
        cmdsys command parser.

        response_handle is the ResponseManager instance for this session.
        command_string is the command that is being handled currently.
        arguments are the remaining arguments.
        command_list is an iterable of Command instances supported for this call.
        client is the discord client instance.
        """

        for command in command_list:
            if command_string in command.names:

                if response_handle.is_chat():
                    # chat commands
                    if not command.allowChat:
                        raise PermissionDeniedException("This command is not available in chat.")
                    # only check permissions if the user is not the owner
                    if response_handle.getID() != client.config.getElementInt("bot.owner"):
                        if command.ownderOnly:
                            # owner only command
                            if response_handle.getID() == 181072803439706112:
                                raise PermissionDeniedException("Sorry Aidan, but I cannot let you do that.")
                            else:
                                raise PermissionDeniedException(interaction.denied.getRandom())
                        elif not (response_handle.getID() in SUPERUSERS or response_handle.getPermission().is_superset(command.permissions)):
                            # insufficient permissions
                            raise PermissionDeniedException("You do not have sufficient permission to use this command.")

                        if response_handle.getMessage().guild:
                            db = client.db.getServer(response_handle.getMessage().guild.id)

                            ds = db.createDatasetIfNotExists("blockedUsers", {"userID": response_handle.getMessage().author.id})
                            if ds.exists(): #FOUND YOU
                                raise PermissionDeniedException("You have been blocked from using bot commands. If you believe that this is an error please report this to the bot owner.")

                else:
                    if not command.allowConsole:
                        raise PermissionDeniedException("This command is not available on console.")

                # process arguments

                if command.subcommands:
                    new_command = arguments[0]
                    if len(arguments) > 1:
                        new_arguments = arguments[1:]
                    else:
                        new_arguments = []
                    try:
                        await self._parse_command(response_handle, client, new_command, new_arguments, command.subcommands)
                    except CommandNotFoundException:
                        self.logger.exception("")
                    else:
                        return

                final_args = []
                arg_c = len(command.arguments)
                for i in range(arg_c):
                    argument = command.arguments[i]
                    if len(arguments) < 1:
                        if not argument.optional:
                            raise CommandCallFailedException("Not enough arguments provided.")
                        else:
                            break # we are out of arguments anyway and the remaining ones should all be optional
                    if arg_c - i < 2:
                        consolidated_argument = " ".join(arguments)
                    else:
                        consolidated_argument = arguments.pop(0)
                    
                    final_args.append(await argument.parse(client, consolidated_argument, response_handle, command))

                command._setVariables(response_handle)
                await command.call(*final_args)
                return

        raise CommandNotFoundException("That command does not exist.")

    async def parse_command(self, response_handle: "ResponseManager", command_list: Iterable[Command], client: "ProtosBot") -> None:

        """
        parse and execute a command.

        response_handle is the ResponseManager instance for this session.
        command_list is an iterable of Command instances supported for this call.
        client is the discord client instance.
        """

        prefix = client.config.getElementText("bot.prefix", "+")

        icons = { #Discord chat icons
            "ok": client.config.getElementText("bot.icons.ok"),
            "forbidden": client.config.getElementText("bot.icons.forbidden"),
            "error": client.config.getElementText("bot.icons.error"),
            "pin": client.config.getElementText("bot.icons.pin")
            }

        cmd_s = await response_handle.getCommand()
        if response_handle.is_chat():
            cmd_s = cmd_s[len(prefix):]

        tokens = shlex.split(cmd_s)

        if len(tokens) < 1:
            return #empty string

        cmd = tokens[0].lower()
        if len(tokens) > 1:
            args = tokens[1:]
        else:
            args = []

        if cmd in self.HELP_COMMAND_ALIASES:
            if not args:
                return await self.print_command_list(command_list, response_handle)
            if await self.get_help(args, command_list, response_handle):
                return
            await response_handle.reply("Unknown command '%s'" % cmd)
            return

        try:
            await self._parse_command(response_handle, cmd, args, command_list, client)
        except CommandCallAbortedException:
            return
        except (ArgumentException, CommandCallFailedException) as e:
            await response_handle.reply("Command execution failed: %s" % str(e))
        except CommandNotFoundException as e:
            await response_handle.reply("Command execution failed: This command does not exist.")
        except CommandException as e:
            await response_handle.reply("Command execution failed: An unknown error occured.")
        except BaseException:
            self.logger.exception("Command execution failed: ")
            if client.config.getElementInt("bot.debug.showCommandErrors", 0, False):
                tb = chatutils.mdEscape(traceback.format_exc())
                await response_handle.reply("Command execution failed:\n %s\n\nYou are receiving this message because command debugging is enabled.\nIt can be disabled in the config files." % tb, True)

        response_handle.close()