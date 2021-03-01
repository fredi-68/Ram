import discord
from cmdsys import *

class Ping(Command):

    def setup(self):

        self.name = "ping"
        self.desc = "A simple ping command"

    async def call(self, **kwargs):
        
        await self.respond("pong", True)
        return