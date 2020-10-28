import discord
from cmdsys import *

class GetARoom(Command):

    FLAVOR_TEXT = """
    I am the admin of my server,
    Pins are my body and emotes are my blood.
    I have created over a thousand channels,
    Unknown to Tatsu,
    Nor known to Aids.
    Have withstood pain to create many roles
    Yet, those hands will never ban anyone.
    So as I pray, *Unlimited Channel Works*.
    """

    def setup(self):

        self.name = "getaroom"
        self.desc = "Go get a room"
        self.permissions.administrator = True

    async def call(self, **kwargs):

        await self.respond(self.FLAVOR_TEXT, True)
        await self.msg.guild.create_voice_channel("UNLIMITED CHANNEL WORKS")