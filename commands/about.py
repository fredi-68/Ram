import discord
from cmdsys import *

from version import S_TITLE_VERSION

ABOUT_TEXT = """
%s

Copyright (c) 2019 fredi_68
All rights reserved.

Privacy statement: https://docs.google.com/document/d/15IiNtU491MO5ArmX_nBaqIljGDDdf86J9MTJU_eYk6w/edit?usp=sharing

Contact support: %s
"""

class About(Command):

    def setup(self):

        self.name = "about"
        self.aliases.append("contact")
        self.aliases.append("info")
        self.desc = "Get information about this bot."

    async def call(self, **kwargs):

        ownerID = self.config.getElementText("bot.owner")
        owner = await self.client.get_user_info(ownerID)
        support_info = "%s#%s (UID: %s)" % (owner.name, str(owner.discriminator), ownerID)
        text = ABOUT_TEXT % (S_TITLE_VERSION, support_info)
        await self.respond(text)