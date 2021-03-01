import random

import discord
from cmdsys import *

MESSAGE = 685245163555258372

class MyCommand(Command):

    def setup(self):

        self.name = "thelist"
        self.desc = "Ask The List (tm) for a game to play."
        self.allowConsole = False

    async def call(self, **kwargs):

        try:
            msg = await self.msg.channel.fetch_message(MESSAGE)
        except:
            await self.respond("Could not fetch The List (tm), are you in the correct channel?", True)
            return

        entries = list(map(lambda x: x.split("-", 1), msg.content.split("\n")))

        choice = random.choice(entries)

        e = discord.Embed(
            title="Result: %s" % choice[0],
            description=choice[1]
            )
        await self.embed(e)