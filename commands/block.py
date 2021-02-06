from xml.etree import ElementTree as ET

import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):
        
        self.name = "block"
        self.desc = "Blocks a user from using bot commands."
        self.addArgument(MemberArgument("member"))
        self.ownerOnly = True
        self.hidden = True

    async def call(self, member, **kwargs):

        if not isinstance(member, discord.Member):
            await self.respond("Not a valid member.")
            return

        if self.config.getElementInt("bot.owner", -1) == member.id:
            await self.respond("You can't block the bot owner!", True)
            return

        db = self.db.getDatabaseByMessage(self.msg)
        
        ds = db.createDatasetIfNotExists("blockedUsers", {"userID": member.id})
        if ds.exists():
            await self.respond("This user is already blocked.", True)
            return

        ds.update() #block user
        await self.respond("Successfully blocked user " + member.name + " (" + str(member.id) + ")", True)
        return