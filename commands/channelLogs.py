import discord
from cmdsys import *

from core_models import AuditLogChannel

class ChannelLogs(Command):

    def setup(self):

        self.name = "cal"
        self.aliases.append("channelAuditLog")
        self.aliases.append("chLog")
        self.desc = "Manage audit log channels.\nAction can be either 'add' or 'remove'. If channel isn't specified, it defaults to the current channel."
        self.addArgument(StringArgument("action"))
        self.addArgument(ChannelArgument("channel", True))
        self.permissions.administrator = True

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
        q = db.query(AuditLogChannel).filter(channel_id=channel.id)
        m = db.new(AuditLogChannel)
        m.channel_id = channel.id

        if action == "add":
            if q:
                await self.respond("This channel is already marked as audit log channel.", True)
                return

            m.save()
            await self.respond("Successfully marked channel "+channel.name+" as audit log channel.")
            return

        elif action == "remove":
            if not q:
                await self.respond("Cannot remove this channel since it isn't an audit log channel.", True)
                return

            q.delete()
            await self.respond("Successfully removed audit log channel "+channel.name)
            return

        else:
            await self.respond("Action must be either 'add' or 'remove'.", True)
            return
