from math import *

import discord
from cmdsys import *

class EvalCmd(Command):

    def setup(self):

        self.name = "eval"
        self.desc = "Process expressions."
        #self.permissions.administrator = True
        self.ownerOnly = True
        self.addArgument(Argument("expression", CmdTypes.STR))

    async def call(self, expression, **kwargs):

        if expression.find("\n") > -1:

            #no you don't inject your fucking code here
            await self.respond("What exactly are you trying to do?", True)

        else:
            try:
                res = eval(expression)
                await self.respond("Result: %s" % str(res), True)
            except Exception as e:
                await self.respond("There was an error in your expression: %s" % str(e), True)
