import shlex

import discord

from cmdsys import *
from audio import FFMPEGSound, AudioError

class FFMPEGCommand(Command):

    def setup(self):

        self.name = "ffmpeg"
        self.desc = "Low level interface for creating and playing ffmpeg sounds. For more information see ffmpeg.org"
        self.aliases.append("ffplay")
        self.addArgument(Argument("target", CmdTypes.STR))
        self.addArgument(Argument("options", CmdTypes.STR, True))
        self.ownerOnly = True
        self.allowConsole = False

    async def call(self, target, options=""):

        try:
            ch = self.msg.server.voice_client.channel
        except AttributeError:
            await self.respond("unable to play FFMPEG sound: Not connected to a voice channel on this server.", True)
            return

        try:
            snd = FFMPEGSound(target, shlex.split(options))
        except AudioError as e:
            await self.respond("unable to create FFMPEG sound instance: %s" % str(e), True)
            return

        try:
            self.playSound(snd, ch)
        except AudioError as e:
            await self.respond("unable to play FFMPEG sound on channel %s: %s" % (ch.name, str(e)), True)
            return

        await self.respond("Queued **%s**." % target)