import discord
from cmdsys import *

class MyCommand(Command):
    
    def setup(self):
        
        self.name = "nick"
        self.desc = "Change the nickname of a member."
        self.permissions.administrator = True
        self.addArgument(MemberArgument("member"))
        self.addArgument(StringArgument("name"))

    async def call(self, member, name, **kwargs):

        if not isinstance(member, discord.Member):
            await self.respond("Not a valid member ID!",True)
            return
        await member.edit(nick=name)