import discord
from cmdsys import *

LINK = "https://uploads.disquscdn.com/images/88bdde16848bcc37c7f626390a0de9044c17ad93bba379664930a631caed1e55.gif"

class MyCommand(Command):

    def setup(self):

        self.name = "hmm"
        self.desc = "HMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMmmmmmmmmmmmmmmm..."
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
