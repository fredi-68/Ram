import discord
import version
from cmdsys import *

class Stats(Command):

    def setup(self):

        self.name = "stats"
        self.desc = "Show operational statistics for this shard."

    async def call(self, **kwargs):

        e = discord.Embed(title="ProtOS Bot Statistics")

        has_ytdl = True
        try:
            import youtube_dl
            del youtube_dl
        except:
            has_ytdl = False

        has_imglib = True
        try:
            import imagelib
            imagelib.init(do_raise=True)
            del imagelib
        except:
            has_imglib = False

        generalInformation = (
            "Name: %s    " % self.client.user.name,
            "UID: %s    " % self.client.user.id,
            "Version: %s    " % version.S_VERSION,
            "Shard: %i/%i    " % ((self.client.shard_id if self.client.shard_id else 0)+1, (self.client.shard_count if self.client.shard_count else 1)),
            "AI Backend: %s" % (self.client.cs.name),
            "Music Backend: %s" % ("youtube_dl" if has_ytdl else "Unavailable"),
            "Image Processing Backend: %s" % ("imagelib" if has_imglib else "Unavailable"),
            "Database Backend: %s" % environment.database._engine.__name__
            )
        e.add_field(name="General Information:", value="\n".join(generalInformation), inline=True)

        discordInformation = (
            "Discord.py Version: %s" % discord.__version__,
            "Server Count: %i    " % len(list(self.client.guilds)),
            "Member Count: %i    " % len(list(self.client.get_all_members())),
            "Channel Count: %i    " % len(list(self.client.get_all_channels())),
            "Emoji Count: %i    " % len(list(self.client.emojis))
            )
        e.add_field(name="Discord Related:", value="\n".join(discordInformation), inline=True)

        aiState = self.config.getElementText("bot.chat.aistate", "unknown", False).upper()

        settings = (
            "AI State: %s" % aiState,
            "Voice Receive Hooks: %s" % ("Enabled" if self.client.voice_receive is not None else "Disabled")
            )
        e.add_field(name="Settings:", value="\n".join(settings), inline=True)

        await self.embed(e)
