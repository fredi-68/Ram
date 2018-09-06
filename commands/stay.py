import random

import discord
from cmdsys import *

#This is a fake command that I made in response to aidan making a related joke once

class MyCommand(Command):

    def setup(self):

        self.name = "stay"
        self.desc = "Stay a while and listen."
        self.hidden = True

    async def call(self, **kwargs):

        if self.responseHandle.getID() == "205327762628542464":
            await self.respond("I'm always here for you, master.",True)
            return

        await self.respond("Sorry, but I don't love you.",True)