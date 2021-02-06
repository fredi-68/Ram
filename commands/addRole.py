import discord
from cmdsys import *

#TODO: Make this use the database instead
WHITELISTED_ROLE_IDS = [
    383998414225932288
    ]

class MyCommand(Command):

    def setup(self):
        
        self.name = "addrole"
        self.aliases.append("giverole")
        self.desc = "Add a self assignable role to your member account."
        self.addArgument(StringArgument("role"))
        self.allowConsole = False

    async def call(self, role, **kwargs):

        for i in self.msg.guild.roles:
            if i.name == role and i.id in WHITELISTED_ROLE_IDS:
                role = i

        if isinstance(role, str): #If the role is still a string we didn't find any actual role with that name
            await self.respond("There is no such role on this server or role is not self assignable!", True)
            return

        try:
            await self.msg.author.add_roles(role)
        except discord.DiscordException:
            await self.respond("An error occured while assigning roles. Perhaps you have already been assigned this role?", True)
            return
        await self.respond("Successfully assigned role " + role.name + " to your member account!", True)