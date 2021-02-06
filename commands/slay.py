import random

import discord
from cmdsys import *

WEAPON_TEXTS = [
    "using a rusty knife",
    "using a high quality sword",
    "with a deep thrust of a pork sword",
    "by slitting his throat and fucking the wound",
    "using fucking twin daggers",
    "using a giant dildo",
    "using Doomfists gauntlet",
    "by sitting on their face",
    "by picking Hanzo in quickplay",
    "using Aidans english dictionary",
    "using a Hatchet",
    "by pushing them off Pys giant Minecraft tower",
    "using a swift swing of their golf club",
    "using Aidans dirty buttplug",
    "for no apparent reason",
    "because they didn't like the beatles",
    "with an intense fingerbang",
    "while they were just trying to play the piano. Bit harsh",
    "with a pringles can",
    "by taking high ground",
    "until they died from it",
    ". Finally"
    ]

ACTION_TEXT = [
    "killed",
    "brutally slayed",
    "absolutely destroyed",
    "completely annihilated",
    "disintegrated",
    "dismembered",
    "golfed",
    "passed the whisky to",
    "blue balled",
    "ended the sad life of",
    "blew up",
    "stabbed",
    "solo ulted",
    "360-noscoped",
    "decapitated",
    "massacred",
    "gave it to",
    "terminated",
    "shredded",
    "slapped",
    "really badly hurt",
    "smashed",
    "crucified"
    ]

class MyCommand(Command):

    def setup(self):

        self.name = "slay"
        self.desc = "Slay someone (or something)."
        self.aliases = ["annihilate", "destroy", "kill"]
        self.addArgument(StringArgument("victim"))
        self.allowConsole = False

    async def call(self, victim, **kwargs):

        await self.respond("%s %s %s %s." % (self.msg.author.mention, random.choice(ACTION_TEXT), victim, random.choice(WEAPON_TEXTS)))