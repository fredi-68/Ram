import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "embed"
        self.desc = "Embed test command"
        self.addArgument(Argument("title",CmdTypes.STR))
        self.addArgument(Argument("desc",CmdTypes.STR))
        self.addArgument(Argument("color",CmdTypes.INT))
        self.ownerOnly = True
        self.hidden = True

    async def call(self, title, desc, color, **kwargs):

        e = discord.Embed(title=title,description=desc,color=color)
        e.set_author(name=self.client.user.name)
        
        e.add_field(name="a test field", value="a test value", inline=True)

        await self.embed(e)