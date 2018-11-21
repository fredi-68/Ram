import os
import functools
import asyncio

import discord

from cmdsys import *
from audio import FFMPEGSound
from ytsearch import YouTubeSearch, SoundCloudSearch
import chatutils

HAS_YTDL = True
try:
    import youtube_dl
    from youtube_dl.extractor.soundcloud import SoundcloudIE
except ImportError:
    HAS_YTDL = False

YOUTUBE_DL_OPTIONS = {
    "format": "webm[abr>0]/bestaudio/best",
    "prefer_ffmpeg": True,
    "nocheckcertificate": True #nocheckcertificate is necessary for this to work on the AWS server for some reason...
    }
YOUTUBE_DL_EXTRACT_OPTIONS = {
    "download": False
    }

SELECT_EMOTES = {
    "0⃣": 0,
    "1⃣": 1,
    "2⃣": 2,
    "3⃣": 3,
    "4⃣": 4,
    "5⃣": 5,
    "6⃣": 6,
    "7⃣": 7,
    "8⃣": 8,
    "9⃣": 9
    }

class MyCommand(Command):

    def setup(self):

        self.name = "play"

        self._descLines = [
            "Play music from the local library or online streaming services.",
            "Use +tracks to display a list of all locally available sound files.",
            "",
            "This command features an integrated search engine for finding songs using a search query string. You can use this feature by prefixing your request with a keyword specifying the search engine you want to use.",
            "These search engines keywords are currently recognized:",
            "```",
            "  youtube",
            "  soundcloud",
            "  search (use default, alias for 'youtube'",
            "```"
            ]

        self.desc = "\n".join(self._descLines)
        self.addArgument(Argument("query", CmdTypes.STR))
        self.allowConsole = False

    async def search(self, query, engine, color):

        await self.respond("Searching %s..." % engine.serviceName)
        results = engine.search(query, 10)

        e = discord.Embed(title="%s Search Results" % engine.serviceName, description="", color=discord.Color(color))
        items = list(results.items())
        for i in range(len(results)):
            url, title = items[i]
            e.add_field(name="Result %i: %s" % (i, title), value=url, inline=False)
        e.set_footer(text="Select a track from the list above by clicking the corresponding reaction below this post.")
        msg = await self.client.send_message(self.msg.channel, None, embed=e) #we have to use the long version here, because we need access to the message

        #Add reactions to the message to identify the track
        reactions = list(SELECT_EMOTES.keys())
        for i in range(len(results)):
            await self.client.add_reaction(msg, reactions[i])

        #Wait for user to click one
        selected = await self.client.wait_for_reaction(list(SELECT_EMOTES.keys()), user=self.msg.author, timeout=30, message=msg)
        if selected == None:
            return
        e = selected.reaction.emoji
        if isinstance(e, discord.Emoji):
            e = e.name
        if not e in SELECT_EMOTES:
            return

        #Get the index we want
        index = SELECT_EMOTES[e]

        #Try to remove our reactions from the video
        #(this doesn't currently work, probably because the message.reactions list doesn't get updated.
        #This unfortunately also means that we can't easily fix this since we'd have to manually request the message to be resent.
        #That is, unless we find a way to accessing a new copy of the message somehow...)
        for i in msg.reactions:
            try:
                await self.client.remove_reaction(msg, i, client.user)
            except discord.DiscordException:
                pass

        if index < 0 or index > len(results) - 1:
            await self.respond("Error: Index out of bounds", True)
            return

        return list(results.keys())[index]

    async def call(self, query, **kwargs):

        if not (hasattr(self.msg.server, "voice_client") and self.msg.server.voice_client):
            await self.respond("I'm currently not in a voice channel on this server.", True)
            return

        targetChannel = self.msg.server.voice_client.channel

        #LOCAL MUSIC FILES

        localquery = query.lower() #make query string match all cases
        dir = os.listdir("tracks")
        for i in dir:
            if i.lower().rsplit(".")[0] == localquery:
                sound = FFMPEGSound("tracks/" + i)
                self.playSound(sound, targetChannel)
                await self.respond("Queued %s." % chatutils.mdItalic(i))
                return

        #YOUTUBE_DL

        if HAS_YTDL:

            #TODO: Currently, users could exploit the way the search engines work to add arbitrary query arguments to the HTTP call.
            #Fix this by escaping the query string if YTDL is to be used.

            if localquery.startswith("search "):
                q = query[7:]
                searchEngine = YouTubeSearch(self.config.getElementText("google.api.token"))
                query = await self.search(q, searchEngine, 0xFF0000)
                if not query:
                    return

            elif localquery.startswith("youtube "):
                q = query[8:]
                searchEngine = YouTubeSearch(self.config.getElementText("google.api.token"))
                query = await self.search(q, searchEngine, 0xFF0000)
                if not query:
                    return

            elif localquery.startswith("soundcloud "):
                q = query[11:]
                #Since SoundCloud doesn't allow new client applications right now,
                #we try to use the youtube_dl client ID (which may end up blocked or rate limited very fast)
                searchEngine = SoundCloudSearch(self.config.getElementText("soundcloud.clientID", SoundcloudIE._CLIENT_ID))
                query = await self.search(q, searchEngine, 0xFF5500)
                if not query:
                    return

            #New playlist handling code
            #We need to do youtube_dl handling manually
            await self.respond("Looking for requested resource online...")
            yt = youtube_dl.YoutubeDL(YOUTUBE_DL_OPTIONS)
            try:
                self.logger.debug("Trying to extract youtube stream information...")
                func = functools.partial(yt.extract_info, query, **YOUTUBE_DL_EXTRACT_OPTIONS)
                info = await asyncio.get_event_loop().run_in_executor(None, func)
            except:
                self.logger.exception("YTDL failed: ")
                await self.respond("Couldn't find a file matching your query.", True)
                return

            #consolidate single videos to pseudo playlists
            if "_type" in info and info["_type"] == "playlist":
                await self.respond("Playlist detected at source location, launching experimental playlist handling code.\nExamining source manifest...")
                entries = info["entries"]
            else:
                entries = [info]

            
            listLength = len(entries)
            await self.respond("%i source %s found, downloading..." % (listLength, ("entries" if listLength > 1 else "entry")))
            i = 0
            for track in entries:
                i += 1
                self.logger.debug("Queuing entry %i of %i total: %s" % (i, listLength, track["webpage_url"]))

                url = track["url"]
                author = track["uploader"] if "uploader" in track else "Unknown"
                title = track["title"] if "title" in track else "Untitled"

                sound = FFMPEGSound(track["url"], author=author, title=title)
                self.playSound(sound, targetChannel)

            await self.respond("Queued %i track(s)." % i)
            return

        await self.respond("Couldn't find a file matching your query.", True)
        return