import discord
from cmdsys import *

LINK = "https://gfycat.com/SecondaryPleasedIchthyosaurs"

class MyCommand(Command):

    def setup(self):

        self.name = "buns"
        self.aliases.append("hair")
        self.desc = "Show appreciation for the wonderful things that are hair buns. WEEBS ONLY."
        self.allowConsole = False

    async def call(self, **kwargs):

        db = self.db.getServer("global") #use some global database

        db.createTableIfNotExists("weebs", {"user": "text"}, True)
        ds = db.createDatasetIfNotExists("weebs", {"user": self.msg.author.id}) #we won't actually alter the database, just want to see if the dataset exists

        if not ds.exists():
            await self.respond("Only believers in the god of anime may use this command.", True)
            return

        #user is already a weeb
        await self.respond(LINK)