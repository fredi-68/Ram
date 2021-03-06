import discord
from cmdsys import *

class MyCommand(Command):
    
    def setup(self):

        self.name = "presence"
        self.desc = "Changes the bots 'presence'. This is usually a game being played or a stream title."
        self.ownerOnly = True
        self.addArgument(IntArgument("type"))
        self.addArgument(StringArgument("game")) #Fixed command signature, allowing for multi word presences

    async def call(self, type, game, **kwargs):

        await self.client.change_presence(activity=discord.Game(name=game, type=type))