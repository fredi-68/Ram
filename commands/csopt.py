import discord
import chatutils
from cmdsys import *

class CSOpt(Command):

    def setup(self):

        self.name = "csopt"
        self._original_desc = "Interface with the conversation simulator.\n\nArgument 'action' should be either 'get' or 'set'"
        self.desc = self._original_desc

        self.ownerOnly = True

        self.addArgument(StringArgument("action"))
        self.addArgument(StringArgument("option"))
        self.addArgument(StringArgument("value", True))

    async def getHelp(self):
        
        #Update command description to include option hints generated from currently active conversation simulator
        res = chatutils.mdCode(await self.client.cs.getOpt("HELP"))
        self.desc = self._original_desc + "\n\nAvailable options for conversation simulator %s:\n%s" % (self.client.cs.name, res)

        return await super().getHelp()

    async def call(self, action, option, value=None):

        action = action.lower()
        if action == "get":
            self.logger.debug("Getting CS option '%s'..." % option)
            try:
                res = str(await self.client.cs.getOpt(option))
            except NotImplementedError:
                await self.respond("This option is not supported by this implementation.", True)
                return
            await self.respond("Value of '%s': '%s'" % (option, res))

        elif action == "set":
            self.logger.debug("Setting CS option '%s'..." % option)
            try:
                await self.client.cs.setOpt(option, value)
            except NotImplementedError:
                await self.respond("This option is not supported by this implementation.", True)
                return

        else:
            await self.respond("Action must be either 'get' or 'set'.", True)
