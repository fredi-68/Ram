import discord
from cmdsys import *
from audio import AudioError

class MyCommand(Command):

    def setup(self):

        self.name = "volume"
        self.desc = "Set the volume for the active voice channel.\nRun without any arguments to get the current volume of this channel."
        self.allowConsole = False
        self.addArgument(Argument("volume", CmdTypes.FLOAT, True))
        self.addArgument(Argument("server", CmdTypes.SERVER, True))
        self.permissions.administrator = True

    async def call(self, volume=None, server=None, **kwargs):

        #This whole thing is pretty pointless rn since we aren't allowing console to access this command
        if not server:
            if not self.msg:
                await self.respond("You need to specify a server when setting volume from console.")
                return
            server = self.msg.server

        if not (hasattr(server, "voice_client") and server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        db = self.db.getServer(self.msg.server.id)
        db.createTableIfNotExists("voiceClientSettings", {"name": "text", "value": "text"})
        ds = db.createDatasetIfNotExists("voiceClientSettings", {"name": "volume"})

        if volume != None:
            #Set volume
            try:
                ch = self.audioManager.createChannel(server.voice_client.channel)
                self.audioManager.setVolume(server.voice_client.channel, volume)
                await self.respond("Set playback volume to %.0f%%" % (volume * 100))
            except AudioError as e:
                await self.respond("Unable to set volume on channel %s: %s" % (server.voice_client.channel.name, str(e)), True)
            ds.setValue("value", str(volume))
            ds.update()
        else:
            #Get volume
            v = ds.getValue("value")
            if v == "None":
                v = 1.0
            else:
                v = float(v)
            v *= 100 #convert to percent
            await self.respond("Playback volume is is set to %.0f%%" % v)