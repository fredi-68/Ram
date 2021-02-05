import re
import random

import discord
from cmdsys import *

class RollCmd(Command):

    REG_EXPR = re.compile("^(?:([0-9]+)d)?([0-9]+)(?:\+([0-9]+))?$")

    def setup(self):

        self.name = "roll"
        self.aliases.append("r")
        self.desc = """Roll one or multiple dice.

Examples:

To roll a D20 (that is, a 20 sided die), simply type the number:
    */roll 20
    (you can optionally prefix the number with a lowercase d)*

You can roll multiple dice at the same time, by specifying the amount,
followed by a `d` and the amount of sides. Note that only multiple of the
same die can be rolled this way:
    */roll 2d10*

You can add a constant offset to the result by following the roll with a `+`,
followed by the offset.
    */roll 1d8+3*
        """
        self.addArgument(Argument("formula", CmdTypes.STR))

    async def call(self, formula):
        
        match = self.REG_EXPR.match(formula)
        if match is None:
            await self.respond("Invalid die formula.", True)
            return
        
        n, k, o = list(map(lambda x: int(x) if x is not None else 0, match.groups()))

        dice = []
        for i in range(max(n, 1)):
            dice.append(random.randint(1, k))

        await self.respond("%s + %i = %i" % (", ".join(map(str, dice)), o, sum(dice)+o))