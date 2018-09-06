import discord
from cmdsys import *
from audio import AudioError

class MyCommand(Command):

    def setup(self):

        self.name = "volume"
        self.desc = "Set the volume for the active voice channel."
        self.allowConsole = False
        self.addArgument(Argument("volume", CmdTypes.FLOAT))
        self.addArgument(Argument("server", CmdTypes.SERVER, True))
        self.permissions.administrator = True

    async def call(self, volume, server=None, **kwargs):

        if not server:
            if not self.msg:
                await self.respond("You need to specify a server when setting volume from console.")
                return
            server = self.msg.server

        if not (hasattr(server, "voice_client") and server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        try:
            self.audioManager.setVolume(server.voice_client.channel, volume)
        except AudioError as e:
            await self.respond("Unable to set volume on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)