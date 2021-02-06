import discord
import audio
from cmdsys import *

class VoiceLeave(Command):

    def setup(self):

        self.name = "leave"
        self.desc = "Leave the bots current voice channel."

        self.permissions.administrator = True #pylint: disable=assigning-non-slot
        self.addArgument(ServerArgument("server", True))

    async def call(self, server=None):

        if not self.msg:
            if not server:
                await self.respond("Server specification is required for using this command on console!")
                return
        else:
            if not server:
                server = self.msg.guild

        if not server.voice_client:
            await self.respond("Not currently connected to any voice channels on this server.", True)
            return

        await self.respond("Disconnecting, please stand by.", True)
        try:
            self.audioManager.shutdownChannel(server.voice_client.channel) #stop all sounds that are still playing
        except audio.AudioError:
            pass

        await server.voice_client.disconnect() #we need to do this after stopping the sounds, otherwise voice_client is set to None
