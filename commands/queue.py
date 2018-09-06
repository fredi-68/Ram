import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "queue"
        self.aliases.append("showQueue")
        self.desc = "Show the audio queue for the specified channel."
        self.allowConsole = False
        self.addArgument(Argument("channel", CMD_TYPE_CHANNEL, True))

    async def call(self, channel=None, **kwargs):

        if not channel:
            if not self.msg.author.voice_channel:
                await self.respond("You are not in a voice channel. Please specify a channel for me to connect to.", True)
                return
            channel = self.msg.author.voice_channel

        e = discord.Embed(title="Audio queue for channel %s" % channel.name, description="", color=discord.Color(0x6464FF))
        
        queue = list(self.audioManager.getQueue(channel))

        for i in range(len(queue)):
            e.add_field(name="%i. %s - %s" % (i, queue[i].author, queue[i].title), value=queue[i].uri.split("?", 1)[0], inline=False)

        await self.embed(e)