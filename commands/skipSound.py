import discord
import os
from cmdsys import *
from audio import AudioError

class MyCommand(Command):

    def setup(self):

        self.name = "skip"
        self.aliases.append("stop")
        self.desc = """
        Skip the current sound.\n
        \n
        Accepts the following flags:\n
        -force: Will skip the next sound, even if it is unskippable. Owner only.\n
        -all: Will skip all sounds in the queue.
        """
        self.addArgument(Argument("flags", CMD_TYPE_STR, True))
        self.permissions.administrator = True
        self.allowConsole = False

    async def call(self, flags="", **kwargs):

        server = self.msg.server

        if "-force" in flags:
            pass

        if "-all" in flags:
            pass

        if not (hasattr(server, "voice_client") and server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        try:
            self.audioManager.skipSound(server.voice_client.channel)
        except AudioError as e:
            await self.respond("Unable to skip sound on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)