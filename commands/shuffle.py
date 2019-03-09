import os

import discord

from cmdsys import *
from audio import AudioError

class ShuffleCommand(Command):

    def setup(self):

        self.name = "shuffle"
        self.desc = "Shuffles the queue (randomizes playback order)."
        self.permissions.move_members = True
        self.allowConsole = False

    async def call(self):

        server = self.msg.server
        if not (hasattr(server, "voice_client") and server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        try:
            self.audioManager.shuffleQueue(server.voice_client.channel)
        except AudioError as e:
            await self.respond("Unable to shuffle queue on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)
            return
        await self.respond("Shuffled the queue on channel %s" % server.voice_client.channel.name)