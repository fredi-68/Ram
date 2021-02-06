import random

import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "random"
        self.desc = "Chat helper. Posts a random number."
        self.addArgument(IntArgument("lower"))
        self.addArgument(IntArgument("upper"))

    async def call(self, lower, upper, **kwargs):

        await self.respond("How about %i?" % random.randint(min(lower, upper), max(lower, upper)), True)