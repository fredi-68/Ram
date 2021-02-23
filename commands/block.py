from xml.etree import ElementTree as ET

import discord
from cmdsys import *

from core_models import BlockedUser

class BlockUser(Command):

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

        db = self.db.get_db_by_message(self.msg)
        
        if len(db.query(BlockedUser).filter(user_id=member.id)) > 0:
            await self.respond("This user is already blocked.", True)
            return

        m = db.new(BlockedUser)
        m.user_id = member.id
        m.save()
        await self.respond("Successfully blocked user " + member.name + " (" + str(member.id) + ")", True)
        return

class Unblock(Command):

    def setup(self):
        
        self.name = "unblock"
        self.desc = "Unblocks a user from using bot commands."
        self.addArgument(MemberArgument("member"))
        self.ownerOnly = True
        self.hidden = True

    async def call(self, member, **kwargs):

        if not isinstance(member, discord.Member):
            await self.respond("Not a valid member.")
            return

        db = self.db.get_db_by_message(self.msg)
        
        ds = db.createDatasetIfNotExists("blockedUsers", {"userID": member.id})
        q = db.query(BlockedUser).filter(user_id=member.id)
        if len(q) < 1:
            await self.respond("This user can't be unblocked since he was never blocked in the first place.", True)
            return

        q.delete() #unblock user
        await self.respond("Successfully unblocked user "+member.name+" ("+member.id+")",True)
        return