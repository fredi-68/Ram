import discord
import os
import random
from cmdsys import *
from audio import FFMPEGSound

SOUND_DIR = "sounds/"

class MyCommand(Command):

    def setup(self):

        self.name = "lucio"
        self.desc = "Play a random Lucio voiceline."
        self.allowConsole = False

    async def call(self, **kwargs):

        if not (hasattr(self.msg.server, "voice_client") and self.msg.server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.",True)
            return

        dir = os.listdir(SOUND_DIR+"lucio")
        line = random.choice(dir)
        sound = FFMPEGSound(SOUND_DIR+"lucio/"+line)
        self.playSound(sound, self.msg.server.voice_client.channel, False)