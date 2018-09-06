import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "weeb"
        self.desc = "Show someone the way of the weeb."
        self.addArgument(Argument("member", CmdTypes.MEMBER))
        self.ownerOnly = True
        self.hidden = True

    async def call(self, member, **kwargs):

        if isinstance(member, str):
            try:
                member = self.msg.server.get_member(member)
            except:
                await self.respond("member must be a valid member ID", True)
                return
        elif not isinstance(member, discord.Member):
            await self.respond("member must be a valid member ID", True)
            return

        db = self.db.getServer("global") #use some global database

        db.createTableIfNotExists("weebs", {"user": "text"}, True)
        ds = db.createDatasetIfNotExists("weebs", {"user": member.id})
        if ds.exists():
            #user is already a weeb. FCKIN WEB LULZ
            await self.respond("That user is already a filthy weeb.", True)
            return
        ds.update() #insert user into database
        await self.respond("User "+member.name+" has been marked as a follower of The Power Of Anime. Congratulations "+member.mention+" , you are now a weeb.")
