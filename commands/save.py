import discord
from cmdsys import *

class Save(Command):

    def setup(self):

        self.name = "save"
        self.desc = "Save the current configuration."

        self.ownerOnly = True

    async def call(self):
        
        await self.client.save()
        await self.respond("Configuration saved.", True)