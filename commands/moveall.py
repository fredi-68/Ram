import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "moveall"
        self.desc = "Move all members in a voice channel to a different voice channel."
        self.addArgument(ChannelArgument("fromCh"))
        self.addArgument(ChannelArgument("toCh"))
        self.permissions.administrator = True

    async def call(self, fromCh, toCh, **kwargs):

        if not (fromCh.type == discord.ChannelType.voice and toCh.type == discord.ChannelType.voice):

            await self.respond("Origin and destination channels must be voice channels!",True)
            return

        if len(fromCh.members) <= 0:

            await self.respond("There is no one in this channel!",True)
            return

        for i in list(fromCh.members): #Make sure the iterator doesn't change its content while moving members (this leads to only half the members getting moved)

            await i.edit(voice_channel=toCh)

        return