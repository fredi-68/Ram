import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "assert"
        self.desc = "Process logic instructions."
        self.permissions.administrator = True
        self.addArgument(Argument("statement", CmdTypes.STR))

    async def call(self, statement, **kwargs):

        if statement.find("\n") > -1:

            #no you don't inject your fucking code here
            await self.respond("What exactly are you trying to do?", True)

        else:
            try:
                exec("assert " + statement)
                await self.respond("True dat.", True)
            except AssertionError:
                await self.respond("Your statement is beyond the rules of logic.", True)
            except:
                await self.respond("Does not compute.", True)