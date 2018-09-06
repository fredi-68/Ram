import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "sAIst"
        self.aliases.append("setAIState")
        self.aliases.append("AIState")
        self.desc = "Set the operation mode of the conversation simulator.\nValid states are 'active', 'passive' and 'off'"
        self.ownerOnly = True
        self.addArgument(Argument("state", CMD_TYPE_STR))

    async def call(self, state, **kwargs):

        state = state.lower()
        if not state in ("active", "passive", "off"):
            await self.respond("State must be one of 'active', 'passive' or 'off'", True)
            return

        self.config.setElementText("bot.chat.aistate", state)
        await self.respond("Operation mode changed to '%s'" % state)