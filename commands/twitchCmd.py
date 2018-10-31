import discord
from cmdsys import *

import twitch

class MyCommand(Command):

    def setup(self):
        
        self.name = "twitch"
        self.desc = "Posts a link to your twitch page and what game you are playing. Stream has to be live for it to work."
        self.addArgument(Argument("channel", CmdTypes.STR))
        self.allowConsole = False
        self._twitchClient = None

    async def call(self, channel, **kwargs):

        if not self._twitchClient:
            self._twitchClient = twitch.TwitchClient(self.config) #cache our client so we don't have to authenticate every time we access the twitch API
        game = self._twitchClient.getChannelGame(channel) #Uses our twitch integration to figure out the game that is being played
        if game:
            await self.client.send_message(self.msg.channel, self.msg.author.mention+" is streaming **"+game+"** at https://www.twitch.tv/"+channel) #guessing the channel link usually works pretty well
        else: #This should never happen now that we are checking the channel page instead of the stream. If it does, the error is in Twitches API so our error message is not helpful anyway.
            await self.client.send_message(self.msg.channel, "That channel appears to be offline right now. Try again in a minute.") #Since the API can take a few minutes to update we tell the user to be patient instead of just telling them off
