import discord
from cmdsys import *

LINK = "https://cdn.discordapp.com/attachments/328154495697682444/410061750436888576/aa6ddb3424502c39605e6859b5cc89d2dd737cdc62910218c801936adcf5434b.gif"

class MyCommand(Command):

    def setup(self):

        self.name = "culture"
        self.desc = "Show that you are a cultured individual. WEEBS ONLY."
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