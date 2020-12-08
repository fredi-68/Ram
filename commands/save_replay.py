import discord
from cmdsys import *
from audio import PCMSound

class CmdSaveReplay(Command):

    def setup(self):

        self.name = "saveReplay"
        self.desc = "Save a 10 second replay of the current voice channel."
        self.allowConsole = False

    async def call(self, **kwargs):

        if self.client.voice_receive is None:
            await self.respond("Voice receive hooks are disabled, this command is not available.", True)
            return

        if not (hasattr(self.msg.guild, "voice_client") and self.msg.guild.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.",True)
            return

        ch = self.msg.guild.voice_client.channel

        sound = PCMSound(self.client.voice_receive.getReplay(ch))
        self.playSound(sound, ch, False)
