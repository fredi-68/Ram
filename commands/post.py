import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):
        
        self.name = "post"
        self.desc = "Posts a message to a channel."
        self.addArgument(Argument("channel",CmdTypes.CHANNEL))
        self.addArgument(Argument("message",CmdTypes.STR))
        self.allowChat = False
        self.hidden = True

    async def call(self, channel, message, **kwargs):

        logger.debug(channel, message)
        await self.client.send_message(channel, message) #I can't believe how simple this is now