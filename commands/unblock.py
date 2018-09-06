from xml.etree import ElementTree as ET

import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):
        
        self.name = "unblock"
        self.desc = "Unblocks a user from using bot commands."
        self.addArgument(Argument("member", CmdTypes.MEMBER))
        self.ownerOnly = True
        self.hidden = True

    async def call(self, member, **kwargs):

        if not isinstance(member, discord.Member):
            await self.respond("Not a valid member.")
            return

        db = self.db.getDatabaseByMessage(self.msg)
        
        ds = db.createDatasetIfNotExists("blockedUsers", {"userID": member.id})
        if not ds.exists():
            await self.respond("This user can't be unblocked since he was never blocked in the first place.", True)
            return

        ds.delete() #unblock user
        await self.respond("Successfully unblocked user "+member.name+" ("+member.id+")",True)
        return