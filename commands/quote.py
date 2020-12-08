import discord
from interaction import QuoteManager
from chatutils import mdCode
from cmdsys import *

QUOTE_MANAGER = QuoteManager()

class CmdQuote(Command):

    def setup(self):

        self.name = "quote"
        self.aliases.append("qt")
        self._original_desc = "Access member quote storage."
        self.desc = self._original_desc
        self.addArgument(Argument("user", CmdTypes.STR, True))
        self.addArgument(Argument("mode", CmdTypes.STR, True))
        self.addArgument(Argument("quote", CmdTypes.STR, True))

    async def getHelp(self):
        
        #Update command description to include a list of all quote stores
        res = mdCode(", ".join(QUOTE_MANAGER.files.keys()))
        self.desc = self._original_desc + "\n\nAvailable quote sources:\n%s" % res

        return await super().getHelp()

    async def call(self, user=None, quote=None, mode=None, **kwargs):

        if not user:
            q = QUOTE_MANAGER.getRandom()
            if not q:
                await self.respond("I don't know any quotes yet. Try adding some using 'quote add'!", True)
                return
            await self.respond(q)
            return
        if mode == "add":
            if not quote:
                await self.respond("You have to specify a message to add as a quote!", True)
                return
            i = QUOTE_MANAGER.addQuote(user.lower(), quote)
            if i or isinstance(i, int):
                await self.respond("Successfully added quote!", True)
                return
            await self.respond("Failed to add quote.", True)
            return
        if mode:
            try:
                mode = int(mode)
            except:
                await self.respond("Not a valid quote index!", True)
                return
            q = QUOTE_MANAGER.getQuote(user.lower(), mode)
            if q:
                await self.respond(q)
            return
        q = QUOTE_MANAGER.getRandomByName(user)
        if q:
            await self.respond(q)
        return
