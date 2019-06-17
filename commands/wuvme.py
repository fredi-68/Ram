import discord
from cmdsys import *

class MyCommand(Command):
    
    def setup(self):

        self.name = "wuvme"
        self.desc = "This is a joke. And a pretty bad one at that."
        self.allowConsole = False

    async def call(self, **kwargs):

        try:
            await self.msg.author.edit(nick="Wuv")
        except discord.Forbidden:
            await self.respond("Sorry, I can't do that.", True)
            return
        await self.respond("There you go.", True)