import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):
        
        self.name = "post"
        self.desc = "Posts a message to a channel."
        self.addArgument(ChannelArgument("channel"))
        self.addArgument(StringArgument("message"))
        self.allowChat = False
        self.hidden = True

    async def call(self, channel, message, **kwargs):

        self.logger.debug(channel, message)
        await channel.send(message) #I can't believe how simple this is now