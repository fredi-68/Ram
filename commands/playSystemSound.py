import discord
import os
from cmdsys import *
from audio import FFMPEGSound

BASE_PATH = "sounds/system/"

class MyCommand(Command):

    def setup(self):

        self.name = "psys"
        self.desc = "Play system sound effects. This command is highly experimental!"
        self.allowChat = False
        self.addArgument(Argument("channel", CmdTypes.CHANNEL))
        self.addArgument(Argument("path", CmdTypes.STR))
        self.hidden = True

    async def call(self, channel, path, **kwargs):

        sound = FFMPEGSound(BASE_PATH + path)
        self.playSound(sound, channel, False)