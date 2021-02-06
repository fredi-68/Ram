import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "rt"
        self.aliases.append("roleTimeout")
        self.aliases.append("roleTo")
        self.desc = "Manage the timeout role."
        self.addArgument(RoleArgument("role"))
        self.permissions.administrator = True

    async def call(self, role, **kwargs):

        if not isinstance(role, discord.Role):
            await self.respond("Not a valid role identifier.", True)
            return

        db = self.db.getServer(role.guild.id) #get the server database for this channel (may be a different server than the caller)
        dsList = db.enumerateDatasets("timeoutRole")
        for i in dsList:
            i.delete()
        ds = db.createDatasetIfNotExists("timeoutRole", {"roleID": role.id})
        ds.update()

        await self.respond("successfully changed timeout role to %s" % role.name)