import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "cp"
        self.aliases.append("channelPin")
        self.aliases.append("chPin")
        self.desc = "Manage pin channels.\nAction can be either 'add' or 'remove'. If channel isn't specified, it defaults to the current channel."
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

        db = self.db.getServer(channel.guild.id) #get the server database for this channel (may be a different server than the caller)
        ds = db.createDatasetIfNotExists("pinChannels", {"channelID": channel.id}) #fetch the dataset before action check, because we need it anyways

        if action == "add":
            if ds.exists():
                await self.respond("This channel is already marked as pin channel.", True)
                return

            ds.update()
            await self.respond("Successfully marked channel "+channel.name+" as pin channel.")
            return

        elif action == "remove":
            if not ds.exists():
                await self.respond("Cannot remove this channel since it isn't a pin channel.", True)
                return

            ds.delete()
            await self.respond("Successfully removed pin channel "+channel.name)
            return

        else:
            await self.respond("Action must be either 'add' or 'remove'.", True)
            return
