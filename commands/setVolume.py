import discord
from cmdsys import *
from audio import AudioError

from core_models import VoiceClientSettings

class SetVolume(Command):

    def setup(self):

        self.name = "volume"
        self.desc = "Set the volume for the active voice channel.\nRun without any arguments to get the current volume of this channel."
        self.allowConsole = False
        self.addArgument(FloatArgument("volume", True))
        self.addArgument(ServerArgument("server", True))
        self.permissions.move_members = True

    async def call(self, volume=None, server=None, **kwargs):

        #This whole thing is pretty pointless rn since we aren't allowing console to access this command
        if not server:
            if not self.msg:
                await self.respond("You need to specify a server when setting volume from console.")
                return
            server = self.msg.guild

        if not (hasattr(server, "voice_client") and server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        db = self.db.get_db(server.id)
        q = db.query(VoiceClientSettings).filter(name="volume")
        if q:
            m = q[0]
        else:
            m = db.new(VoiceClientSettings)
            m.name = "volume"

        if volume != None:
            #Set volume
            try:
                ch = self.audioManager.createChannel(server.voice_client.channel)
                self.audioManager.setVolume(server.voice_client.channel, volume)
                await self.respond("Set playback volume to %.0f%%" % (volume * 100))
            except AudioError as e:
                await self.respond("Unable to set volume on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)
            m.value = str(volume)
            m.save()
        else:
            #Get volume
            v = m.value
            if v == "None":
                v = 1.0
            else:
                v = float(v)
            v *= 100 #convert to percent
            await self.respond("Playback volume is is set to %.0f%%" % v)