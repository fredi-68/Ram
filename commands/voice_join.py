import discord
from cmdsys import *

from core_models import VoiceClientSettings

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
        db = self.db.get_db(self.msg.guild.id)
        q = db.query(VoiceClientSettings).filter(name="volume")
        if not q:
            return

        volume = q[0].value
        if volume in (None, "None"): #Some dataset weirdness
            return

        ch = self.audioManager.createChannel(channel)
        ch.setVolume(float(volume))

        return
