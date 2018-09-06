import random

import discord
from cmdsys import *

ANSWERS = [
    "Nope.",
    "No.",
    "Nah.",
    "Not gonna happen.",
    "Never.",
    "Yeah.",
    "Yes.",
    "Ya.",
    "Yup.",
    "Absolutely.",
    "Definitely.",
    "Indeed.",
    "Maybe.",
    "Well, what do you think?",
    "I don't know the answer to that question.",
    "You don't want to know the answer.",
    "Are you sure you want to know?"
    ]

class MyCommand(Command):

    def setup(self):

        self.name = "8ball"
        self.desc = "Ask the magic 8-ball a question. The answer may or may not confuse you."
        self.aliases = ["eightball"]
        self.addArgument(Argument("question",CmdTypes.STR))
        self.allowConsole = False

    async def call(self, question, **kwargs):

        await self.respond(random.choice(ANSWERS), True)