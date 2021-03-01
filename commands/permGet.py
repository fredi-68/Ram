import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "pget"
        self.desc = "Get a members permissions."
        self.aliases.append("permget")
        self.addArgument(MemberArgument("member"))
        self.addArgument(ChannelArgument("channel", True, None))

    async def call(self, member, channel=None, **kwargs):

        if not isinstance(member, discord.Member):
            await self.respond("Not a valid member ID!",True)
            return
        if channel:
            s = "Permissions for '"+member.name+"' in '"+channel.name+"':\n\n"
            for i in member.permissions_in(channel):
                s += "  "+i[0]+": "+str(i[1])+"\n"
            await self.respond(s)
        else:
            s = "Permissions for '"+member.name+"' on '"+server.name+"':\n\n"
            for i in member.guild_permissions:
                s += "  "+i[0]+": "+str(i[1])+"\n"
            await self.respond(s)