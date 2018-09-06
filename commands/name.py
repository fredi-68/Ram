import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "name"
        self.desc = "Change the name of the bot."
        self.ownerOnly = True
        self.addArgument(Argument("username",type=CmdTypes.STR))
        self.addArgument(Argument("password",type=CmdTypes.STR,optional=True))

    async def call(self, username, password="", **kwargs):

        if password:
            await self.client.edit_profile(username=username, password=password)
        else:
            await self.client.edit_profile(username=username)