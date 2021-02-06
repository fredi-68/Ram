import subprocess
import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "spawn"
        self.aliases.append("pspawn")
        self.desc = "Spawn a shell and execute a command."
        self.addArgument(StringArgument("cmd"))
        self.allowChat = False
        self.hidden = True

    async def call(self, cmd, **kwargs):

        try:
            subprocess.Popen(cmd)
            await self.respond("Command execution successfull")
        except:
            await self.respond("An error occured while trying to execute command.")