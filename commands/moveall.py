import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "moveall"
        self.desc = "Move all members in a voice channel to a different voice channel."
        self.addArgument(Argument("fromCh",CmdTypes.CHANNEL))
        self.addArgument(Argument("toCh",CmdTypes.CHANNEL))
        self.permissions.administrator = True

    async def call(self, fromCh, toCh, **kwargs):

        if not (fromCh.type == discord.ChannelType.voice and toCh.type == discord.ChannelType.voice):

            await self.respond("Origin and destination channels must be voice channels!",True)
            return

        if len(fromCh.voice_members) <= 0:

            await self.respond("There is no one in this channel!",True)
            return

        for i in list(fromCh.voice_members): #Make sure the iterator doesn't change its content while moving members (this leads to only half the members getting moved)

            await self.client.move_member(i,toCh)

        return