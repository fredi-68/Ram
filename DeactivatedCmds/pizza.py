#Pizza Command
#
#Author: fredi_68
#
#You want a pizza timer? YOU'VE GOT IT

import discord
from cmdsys import *

import asyncio

class MyCommand(Command):

    def setup(self):

        self.name = "pizza"
        self.aliases.append("pizzaTimer")
        self.aliases.append("pTimer")
        self.desc = "Tells you when your pizza is ready."
        self.allowConsole = False
        self.addArgument(Argument("seconds", CMD_TYPE_INT))

    async def call(self, seconds, **kwargs):

        await asyncio.sleep(seconds)
        await self.respond("Hey, make sure your pizza hasn't burned to a crisp...", True)