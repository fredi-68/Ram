import discord
from cmdsys import *
from audio import AudioError

class MyCommand(Command):

    def setup(self):

        self.name = "queue"
        self.aliases.append("showQueue")
        self.desc = "Show the audio queue for the specified channel."
        self.allowConsole = False
        self.addArgument(Argument("channel", CmdTypes.CHANNEL, True))

    async def call(self, channel=None, **kwargs):

        if not channel:
            if not self.msg.author.voice.channel:
                await self.respond("You are not in a voice channel. Please specify a channel for me to connect to.", True)
                return
            channel = self.msg.author.voice.channel

        try:
            playing = self.audioManager.getPlaying(channel)
        except AudioError:
            await self.respond("There is no audio being played on this channel.")
            return
        if len(playing) > 0:
            e = discord.Embed(title="Now playing on channel '%s':" % channel.name, description="", color=discord.Color(0x6464FF))

            for i in range(len(playing)):
                sound = playing[i]
                e.add_field(name="%i. %s - %s %s" % (i, sound.author, sound.title, ("[Paused]" if self.audioManager.isPaused(channel) else "")), value=sound.uri.split("?", 1)[0], inline=False)

            await self.embed(e)

        queue = list(self.audioManager.getQueue(channel))
        if len(queue) > 0:
            e = discord.Embed(title="Audio queue for channel '%s'" % channel.name, description="", color=discord.Color(0x6464FF))

            for i in range(len(queue)):
                e.add_field(name="%i. %s - %s" % (i+1, queue[i].author, queue[i].title), value=queue[i].uri.split("?", 1)[0], inline=False)

            await self.embed(e)
        else:
            await self.respond("The queue is empty.")