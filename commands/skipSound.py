import discord
import os
from cmdsys import *
from audio import AudioError

class MyCommand(Command):

    def setup(self):

        self.name = "skip"
        self.aliases.append("stop")
        self.desc = """
        Skip the current sound.

        Accepts the following flags:
        -f: Will skip the next sound, even if it is unskippable. Owner only.
        -a: Will skip all sounds in the queue.

        NOTE: To use flags, specifying an explicit index is mandatory.
        """
        self.addArgument(IntArgument("index", True))
        self.addArgument(StringArgument("flags", True))
        self.permissions.move_members = True
        self.allowConsole = False

    async def call(self, index=0, flags="", **kwargs):

        server = self.msg.guild
        force = False

        if not (hasattr(server, "voice_client") and server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        flags = flags.split(" ")

        if "-f" in flags:
            if not self.isOwner():
                await self.respond("This command requires elevated permissions.")
                return
            force = True

        if "-a" in flags:
            try:
                self.audioManager.clearQueue(server.voice_client.channel, force)
            except AudioError as e:
                await self.respond("Unable to clear queue on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)
            return

        try:
            self.audioManager.skipSound(server.voice_client.channel, index, force)
        except AudioError as e:
            await self.respond("Unable to skip sound on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)