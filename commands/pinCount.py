import discord
from cmdsys import *

MAX_PINS = 50 #Discords hard limit on pinned messages

class MyCommand(Command):

    def setup(self):

        self.name = "pinCount"
        self.desc = "Easily determine how many pins are being used in this channel right now.\nUseful for those instances where you're not sure if pinning another message will delete an older one."
        self.allowConsole = False

    async def call(self, **kwargs):

        count = len(await self.msg.channel.pins()) #get the amount of pins in the current channel
        percentage = 100*(count/MAX_PINS)
        await self.respond("Pins used for channel %s: %i/%i (%.1f%%)" % (self.msg.channel.name, count, MAX_PINS, percentage))