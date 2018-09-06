import discord
from cmdsys import *

#+markdown
MARKDOWN_LINES = [
    "**Discord Markdown reference:**\n",
    "*italics* = \\*italics\\*",
    "**bold** = \\*\\*bold\\*\\*",
    "***bold italics*** = \\*\\*\\*bold italics\\*\\*\\*",
    "~~strikeout~~ = \\~\\~strikeout\\~\\~",
    "__underline__ = \\_\\_underline\\_\\_",
    "__*underline italics*__ = \\_\\_\\*underline italics\\*\\_\\_",
    "__**underline bold**__ = \\_\\_\\*\\*underline bold\\*\\*\\_\\_",
    "__***underline bold italics***__ = \\_\\_\\*\\*\\*underline bold italics\\*\\*\\*\\_\\_",
    "",
    "`single line code` = \\`single line code\\`",
    "```multi line code``` = \\`\\`\\`[language] multi line code\\`\\`\\`"
    ]

class MyCommand(Command):

    def setup(self):

        self.name = "markdown"
        self.desc = "Chat helper. Posts a markdown guide for your convenience."

    async def call(self, **kwargs):

        await self.respond("\n".join(MARKDOWN_LINES))