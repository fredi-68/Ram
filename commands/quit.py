import discord
from cmdsys import *

class Quit(Command):

    def setup(self):

        self.name = "quit"
        self.desc = "Shut the bot down."

        self.ownerOnly = True

    async def call(self):
        
        await self.client.shutdown("Owner requested shutdown.")