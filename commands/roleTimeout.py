import discord
from cmdsys import *

from core_models import TimeoutRole

class TimeoutRoleCmd(Command):

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

        db = self.db.get_db(role.guild.id) #get the server database for this channel (may be a different server than the caller)
        db.query(TimeoutRole).delete()
        m = db.new(TimeoutRole)
        m.role_id = role.id
        m.save()

        await self.respond("successfully changed timeout role to %s" % role.name)