import discord
import version
from cmdsys import *

class Version(Command):

    def setup(self):

        self.name = "version"
        self.desc = "Shows the currently running version."

    async def call(self):
        
        await self.respond(version.S_TITLE_VERSION)