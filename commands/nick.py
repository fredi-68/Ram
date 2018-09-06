import discord
from cmdsys import *

class MyCommand(Command):
    
    def setup(self):
        
        self.name = "nick"
        self.desc = "Change the nickname of a member."
        self.permissions.administrator = True
        self.addArgument(Argument("member",CmdTypes.MEMBER))
        self.addArgument(Argument("name",CmdTypes.STR))

    async def call(self, member, name, **kwargs):

        if not isinstance(member, discord.Member):
            await self.respond("Not a valid member ID!",True)
            return
        await self.client.change_nickname(member,name)