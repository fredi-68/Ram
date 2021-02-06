import discord
from cmdsys import *

class VoiceJoin(Command):

    def setup(self):

        self.name = "voice"
        self.desc = "Join the voice channel you are currently in."

        self.addArgument(ChannelArgument("channel", True))

    async def call(self, channel=None):

        if not self.msg:
            if not channel:
                await self.respond("Channel specification is required for using this command on console!")
                return
        else:
            if not channel:
                if not self.msg.author.voice.channel:
                    await self.respond("You are not in a voice channel. Please specify a channel for me to connect to.", True)
                    return
                channel = self.msg.author.voice.channel
        await self.respond("Joining channel now...", True)
        try:
            await channel.connect()
        except discord.errors.DiscordException:
            await self.respond("Failed to join voice channel.", True)
            return

        #Load audio configuration for server
        db = self.db.getServer(self.msg.guild.id)
        db.createTableIfNotExists("voiceClientSettings", {"name": "text", "value": "text"})
        ds = db.createDatasetIfNotExists("voiceClientSettings", {"name": "volume"})
        if not ds.exists():
            return

        volume = ds.getValue("value")
        if volume in (None, "None"): #Some dataset weirdness
            return

        ch = self.audioManager.createChannel(channel)
        ch.setVolume(float(volume))

        return
