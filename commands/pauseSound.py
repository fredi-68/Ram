import discord
from cmdsys import *
from audio import AudioError

class MyCommand(Command):

    def setup(self):

        self.name = "pause"
        self.aliases.append("unpause")
        self.desc = "Pauses/Unpauses the current sound. Works on all sounds."
        self.addArgument(Argument("server", CmdTypes.SERVER, True))
        self.permissions.move_members = True

    async def call(self, server=None, **kwargs):

        if not server:
            if not self.msg:
                await self.respond("You need to specify a server when pausing/unpausing from console.")
                return
            server = self.msg.guild

        if not (hasattr(server, "voice_client") and server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        try:
            self.audioManager.pauseSound(server.voice_client.channel)
        except AudioError as e:
            await self.respond("Unable to pause/unpause audio playback on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)