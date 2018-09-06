import os

import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):

        self.name = "tracks"
        self.aliases.append("listTracks")
        self.desc = "Shows a list of all tracks I know.\nUse +play <sound> to play a track from this list."
        
    async def call(self, **kwargs):

        dir = os.listdir("tracks")
        s = "Track list: \n\n"
        for i in dir:
            s += i+"\n"
        s += "\nInput files without file name extensions. Filenames are NOT case sensitive."
        await self.respond(s)
        return