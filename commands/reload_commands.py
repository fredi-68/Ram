import discord
import time
from cmdsys import *

class ReloadCommands(Command):

    def setup(self):

        self.name = "reloadCommands"
        self.desc = """Reloads ALL commands.\n
WARNING: This command will cause the event loop to block while commands are being reloaded.
As a result, the gateway connection may be interrupted briefly."""

        self.ownerOnly = True

    async def call(self):
        
        await self.respond("Initializing...")
        start = time.time()
        self.client.load_commands()
        await self.respond("Reload completed in %.2f second(s). %i commands loaded." % (time.time()-start, len(self.client.commands)), True)