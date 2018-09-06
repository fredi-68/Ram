import discord
import os
import random
from cmdsys import *
from audio import FFMPEGSound

SOUND_DIR = "sounds/"

class MyCommand(Command):

    def setup(self):

        self.name = "me"
        self.desc = "Play your personal voiceline on request. You have to be in the same channel as me for this to work."
        self.allowConsole = False

    async def call(self, **kwargs):

        if not (hasattr(self.msg.server, "voice_client") and self.msg.server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        targetChannel = self.msg.server.voice_client.channel

        if not (hasattr(self.msg.author, "voice_channel") and targetChannel == self.msg.author.voice_channel):
            await self.respond("You have to be in my voice channel to play your voiceline!", True)
            return

        dir = os.listdir(SOUND_DIR+"voicelines")
        for i in dir:
            if os.path.isdir(SOUND_DIR+"voicelines/" + i) and i == self.msg.author.id: #we have a voiceline for this member
                files = os.listdir(SOUND_DIR+"voicelines/" + i)
                sound = FFMPEGSound(SOUND_DIR + "voicelines/" + i + "/" + random.choice(files))
                self.playSound(sound, targetChannel, False) #Don't sync member voicelines; this may be a bad idea...
                return
        await self.respond("You don't have a voiceline associated with your user ID!", True)
        return