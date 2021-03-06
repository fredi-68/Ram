import discord
import asyncio
from cmdsys import *
from response_manager import RPCResponse

class Sudo(Command):

    def setup(self):

        self.name = "sudo"
        self.desc = "Gain superuser privileges.\n\nThis command allows you to execute other commands from the console (i.e.: with root access) from anywhere."
        self.hidden = True
        self.ownerOnly = True #only the bot owner should ever be able to gain root access
        self.allowConsole = False #having access to this on the console wouldn't make much sense
        self.addArgument(StringArgument("cmd"))
        self._cmd = ""

    async def call(self, cmd):

        self._cmd = cmd.encode()
        responseHandle = RPCResponse(reader=self, writer=self)
        await CommandParser().parse_command(responseHandle, self.client.commands, self.client)

    #Standard bytestream interface methods go here

    async def readline(self):

        return self._cmd

    async def read(self):

        return self._cmd

    def write(self, msg):

        asyncio.get_event_loop().create_task(self.respond(msg.decode(), True))

    def close(self):

        pass

class CmdTempElevate(Command):

    def setup(self):

        self.name = "elevate"
        self.desc = "Elevate a users permission. This command will add an exception to a users permissions that allows them to bypass any command specific permissions.\nThis effect only lasts until the bot restarts."
        self.hidden = True
        self.ownerOnly = True
        self.addArgument(StringArgument("action"))
        self.addArgument(MemberArgument("user"))

    async def call(self, action, user):

        if action == "add":
            SUPERUSERS.add(user.id)
            await self.respond("Added user %s to the list of temporary superusers." % user.name)

        elif action == "remove":
            SUPERUSERS.discard(user.id)
            await self.respond("Removed user %s from the list of temporary superusers." % user.name)

        else:
            await self.respond("Error: action must be 'add' or 'remove', not '%s'." % action, True)
