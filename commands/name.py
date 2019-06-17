import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "name"
        self.desc = "Change the name of the bot."
        self.ownerOnly = True
        self.addArgument(Argument("username",type=CmdTypes.STR))

    async def call(self, username, **kwargs):

        await self.client.user.edit(username=username)