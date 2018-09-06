import os

import discord
from cmdsys import *

class MyCommand(Command):

    def setup(self):
        
        self.name = "avatar"
        self.desc = "Upload an image to discord as a profile picture"
        self.ownerOnly = True
        self.addArgument(Argument("filename", CmdTypes.STR))

    async def call(self, filename, **kwargs):

        #Will try to upload a profile picture
        if not os.path.isfile(filename):
            await self.respond("File not found.", True)
            return
        f = open(filename, "rb") #open image file for binary data transfer
        try:
            await self.client.edit_profile(avatar=f.read()) #we don't buffer things which is probably bad
            #wait for image to upload
        except discord.InvalidArgument:
            await self.respond("Image format not recognized.", True) #well fuck this should never happen
        f.close()