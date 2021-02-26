import discord
from cmdsys import *

from core_models import BlockedChannel

class ChannelBan(Command):

    def setup(self):

        self.name = "cb"
        self.aliases.append("channelBan")
        self.aliases.append("chBan")
        self.desc = "Manage channel bans.\nAction can be either 'ban' or 'unban'. If channel isn't specified, it defaults to the current channel."
        self.addArgument(StringArgument("action"))
        self.addArgument(ChannelArgument("channel", True))
        self.ownerOnly = True

    async def call(self, action, channel=None, **kwargs):

        if channel == None:
            if self.msg == None:
                await self.respond("Must specify a channel on console!")
                return

            channel = self.msg.channel #use the channel of the caller

        elif not isinstance(channel, discord.TextChannel):
            await self.respond("Not a valid channel identifier.", True)
            return

        db = self.db.get_db(channel.guild.id) #get the server database for this channel (may be a different server than the caller)
        q = db.query(BlockedChannel).filter(channel_id=channel.id)
        m = db.new(BlockedChannel)
        m.channel_id = channel.id

        if action == "ban":
            if q:
                await self.respond("This channel is already banned.", True)
                return

            m.save()
            await self.respond("Successfully banned channel "+channel.name)
            return

        elif action == "unban":
            if not q:
                await self.respond("Cannot unban this channel since it isn't banned.", True)
                return

            q.delete()
            await self.respond("Successfully unbanned channel "+channel.name)
            return

        else:
            await self.respond("Action must be either 'ban' or 'unban'.", True)
            return
