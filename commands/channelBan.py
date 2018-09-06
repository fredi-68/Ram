import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "cb"
        self.aliases.append("channelBan")
        self.aliases.append("chBan")
        self.desc = "Manage channel bans.\nAction can be either 'ban' or 'unban'. If channel isn't specified, it defaults to the current channel."
        self.addArgument(Argument("action", CmdTypes.STR))
        self.addArgument(Argument("channel", CmdTypes.CHANNEL, True))
        self.ownerOnly = True

    async def call(self, action, channel=None, **kwargs):

        if channel == None:
            if self.msg == None:
                await self.respond("Must specify a channel on console!")
                return

            channel = self.msg.channel #use the channel of the caller

        elif not isinstance(channel, discord.Channel):
            await self.respond("Not a valid channel identifier.", True)
            return

        db = self.db.getServer(channel.server.id) #get the server database for this channel (may be a different server than the caller)
        ds = db.createDatasetIfNotExists("blockedChannels", {"channelID": channel.id}) #fetch the dataset before action check, because we need it anyways

        if action == "ban":
            if ds.exists():
                await self.respond("This channel is already banned.", True)
                return

            ds.update()
            await self.respond("Successfully banned channel "+channel.name)
            return

        elif action == "unban":
            if not ds.exists():
                await self.respond("Cannot unban this channel since it isn't banned.", True)
                return

            ds.delete()
            await self.respond("Successfully unbanned channel "+channel.name)
            return

        else:
            await self.respond("Action must be either 'ban' or 'unban'.", True)
            return