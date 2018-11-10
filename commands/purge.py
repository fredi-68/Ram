import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "purge"
        self.desc = "Purges all messages up to a specific message."
        self.permissions.manage_messages = True
        self.addArgument(Argument("message", CmdTypes.MESSAGE))
        self.addArgument(Argument("user", CmdTypes.MEMBER, True))
        self.allowConsole = False

        self.allowDelimiters = False

    async def call(self, message, user=None, **kwargs):

        def check(m):
            return (not user) or m.author == user

        #FIXME: This will NOT work once we switch to a normal user account since purging is bot only.
        #We need a workaround in case a non bot account is used, using normal delete calls
        ret = len(await self.client.purge_from(message.channel, limit=500, after=message, check=check))

        await self.respond(str(ret) + " message(s) deleted.")

        await self.log("User %s purged %i message(s) from channel %s" % (self.msg.author.name, ret, self.msg.channel.name))