import discord
from cmdsys import *

class MyCommand(Command):
    
    def setup(self):

        self.name = "presence"
        self.desc = "Changes the bots 'presence'. This is usually a game being played or a stream title."
        self.ownerOnly = True
        self.addArgument(Argument("type", CmdTypes.INT))
        self.addArgument(Argument("game", CmdTypes.STR)) #Fixed command signature, allowing for multi word presences

    async def call(self, type, game, **kwargs):

        await self.client.change_presence(game=discord.Game(name=game, type=type))