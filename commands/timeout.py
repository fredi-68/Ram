import atexit
import asyncio

import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "timeout"
        self.aliases.append("to")
        self.desc = "Gives the targeted user a timeout role for a variable amount of time (the default is 10 minutes).\nOptional duration parameter specifies the length of the timeout in minutes.\nAll timeouts will be lifted upon bot termination.\n\nTimeout role can be configured using the 'rt' command (admin only)"
        self.permissions.kick_members = True
        self.addArgument(MemberArgument("member"))
        self.addArgument(IntArgument("duration", True))

        self.allowDelimiters = False

        self.timeouted = []
        cleanUpRegister(self.cleanUp)

    async def cleanUp(self):

        #make sure that timeouted members get there timeouts removed if the bot exits for some reason
        for i in self.timeouted:
            await self.removeRole(i, 0) #simulate a timeout with a duration of 0 to instantly remove role

    async def call(self, member, duration=10, **kwargs):

        if not isinstance(member, discord.Member):
            try:
                member = self.msg.guild.get_member(member)
            except:
                await self.respond("Not a valid member ID. Perhaps this ID is referring to a different server?", True)
                return

        try:
            role = await self.getRole()
            if not role:
                await self.respond("An error occured while attempting to time out %s: Role could not be found." % member.name)
                return
            #do timeout
            await member.add_roles(role)
            self.timeouted.append(member)

            self.client.loop.create_task(self.removeRole(member, duration))
            await self.respond("Timed %s out for %i minute(s)." % (member.name, duration))

            db = self.db.getServer(self.msg.guild.id)
            ds = db.createDatasetIfNotExists("timeoutCount", {"userID":member.id})
            ds.setValue("count", ds.getValue("count") + 1)
            ds.update()

            await self.log("User %s timed %s out for %i minutes in channel %s. This user has accumulated %i timeouts." % (self.msg.author.name, member.name, duration, self.msg.channel.name, ds.getValue("count")))

        except BaseException as e:
            await self.respond("An error occured while attempting to time out %s: %s" % (member.name, str(e)), True)

    async def removeRole(self, member, duration):

        await asyncio.sleep(duration * 60) #wait until the timeout is over
        try:
            await member.remove_roles(await self.getRole())
            logger.info("Timeout for %s expired." % member.name)
        except:
            logger.error("Unable to remove timeout for %s." % member.name)

    async def getRole(self):

        db = self.db.getServer(self.msg.guild.id)
        dsList = db.enumerateDatasets("timeoutRole")
        if len(dsList) < 1:
            return None

        name = dsList[0].getValue("roleID")

        for role in self.msg.guild.roles:
            if role.id == name:
                return role