import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "getAvatar"
        self.desc = "Experimental"
        self.allowConsole = False
        self.ownerOnly = True
        self.addArgument(UserArgument("user"))

        self.initLib()

    def initLib(self):

        global imagelib

        try:
            import imagelib
            imagelib.init(True)
        except:
            self.logger.exception("ImageLib couldn't be initialized, this command will not be available.")
            self.allowChat = False

    async def call(self, user=None, **kwargs):

        img = imagelib.fromUserProfile(user)
        await self.client.send_file(self.msg.channel, fp=img, filename=img.name, content="User avatar test message")