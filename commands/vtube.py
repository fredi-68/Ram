import discord
import arrow
import asyncio
import datetime
from urllib import request

from youtube_dl import YoutubeDL, DownloadError
from youtube_dl.extractor.youtube import YoutubeIE, compat_parse_qs
from ics import Calendar

from cmdsys import *

class VTube(Command):

    YOUTUBE_DL_OPTIONS = {
        "format": "webm[abr>0]/bestaudio/best",
        "prefer_ffmpeg": True,
        #"ignoreerrors": True,
        "nocheckcertificate": True #nocheckcertificate is necessary for this to work on the AWS server for some reason...
        }
    YOUTUBE_DL_EXTRACT_OPTIONS = {
        "download": False
        }

    SCHEDULE_SLEEP_INTERVAL = 60 #seconds
    SCHEDULE_UPDATE_FREQUENCY = 1 #per hour
    SCHEDULE_CHECK_FREQUENCY = 60 #per hour

    ICS_URI = "https://sarisia.cc/holodule-ics/holodule-english.ics"
    #ICS_URI = "https://sarisia.cc/holodule-ics/holodule-all.ics"

    def setup(self):

        self.name = "vtubersareshit"
        self.desc = "Fuck you."
        self.permissions.administrator = True

        self.addArgument(Argument("action", CmdTypes.STR))
        self.addArgument(Argument("channel", CmdTypes.CHANNEL, True))

        self._schedule = None
        self._task_runner_handle = self.loop.create_task(self._task_runner())
        cleanUpRegister(self._cleanup)

    async def _task_runner(self):

        """
        Task dispatcher coroutine.
        """

        update_every = datetime.timedelta(hours=1/self.SCHEDULE_UPDATE_FREQUENCY)
        check_every = datetime.timedelta(hours=1/self.SCHEDULE_CHECK_FREQUENCY)

        last_update = arrow.utcnow() - update_every - update_every
        last_check = arrow.utcnow() - check_every - check_every

        while self.loop.is_running():
            now = arrow.utcnow()
            if last_update + update_every < now:
                try:
                    await self._update_schedule()
                except:
                    self.logger.exception("Exception occurred in update_schedule: ")
                last_update = now
            if last_check + check_every < now:
                try:
                    await self._check_schedule(now, last_check)
                except:
                    self.logger.exception("Exception occurred in check_schedule: ")
                last_check = now

            await asyncio.sleep(self.SCHEDULE_SLEEP_INTERVAL)

    async def _update_schedule(self):

        """
        Update the schedule.
        """

        req = request.Request(self.ICS_URI)
        res = await self.loop.run_in_executor(None, lambda: request.urlopen(req))
        self._schedule = Calendar(res.read().decode("utf-8"))
        self.logger.info("Updated schedule: %s" % repr(self._schedule))

    async def _check_schedule(self, now, last):

        """
        Checks the ICS schedule for active events.
        """

        if self._schedule is None:
            return

        for event in self._schedule.events:
            if event.begin <= now:
                if event.begin > last:
                    await self._announce_event(event)

    async def _announce_event(self, event, msg=None):

        """
        Dispatches event notifications.

        event is the ICS Event instance for this event.
        msg is the tracked msg. It is only used for updating delayed streams and not usually set manually.
        """

        if msg is None:
            self.logger.info("Event notification triggered for event %s" % repr(event))
        else:
            self.logger.info("Event %s reevaluation triggered" % repr(event))
        db = self.client.db.getServer("global")
        db.createTableIfNotExists("vtuber_notification_channels", {"channel_id": "int"})
        info = await self._get_info(event)
        for ds in db.enumerateDatasets("vtuber_notification_channels"):
            try:
                ch = await self.client.fetch_channel(ds.getValue("channel_id"))
                mention_role = None
                for role in ch.guild.roles:
                    if role.name == "vtub":
                        mention_role = role
                        break
                if msg is None:
                    msg = await ch.send((mention_role.mention if mention_role is not None else ""), embed=await self._create_embed(event, info))
                elif info.get("is_live"): #only attempt to edit the embed if content has changed.
                    await msg.edit(embed=await self._create_embed(event, info))
            except:
                self.logger.exception("Exception happened in notification dispatcher: ")

        if not info.get("is_live"):

            if arrow.utcnow() > event.end:
                self.logger.error("Event %s has ended, but never went live. Cancelling reevaluation tasks." % repr(event))
                return

            delay = 1/self.SCHEDULE_CHECK_FREQUENCY*60*60
            self.logger.warn("Event %s is running late, scheduling for reevaluation in %f second(s)." % (repr(event), delay))
            
            async def reevaluate():
                await asyncio.sleep(delay)
                await self._announce_event(event, msg=msg)

            self.loop.create_task(reevaluate())

    async def _cleanup(self):

        self._task_runner_handle.cancel()

    async def _get_info(self, event):

        """
        Fallback for when a stream has not yet started.
        """

        title, url = event.description.split("\n", 1)

        ytdl = YoutubeDL(self.YOUTUBE_DL_OPTIONS)
        try:
            info = await self.loop.run_in_executor(None, lambda: ytdl.extract_info(url, **self.YOUTUBE_DL_EXTRACT_OPTIONS))
        except DownloadError:
            info = {"is_live": False}

        info["streamer"] = event.name.split(":", 1)[0]
        info["live_status"] = "is now live" if info.get("is_live") else "will be live shortly"
        info["title"] = title
        info["url"] = url

        return info

    async def _create_embed(self, event, info):

        """
        Turns an ICS event into a Discord embed.
        """

        e = discord.Embed()
        e.title = "%s %s!" % (info.get("streamer"), info.get("live_status"))
        e.add_field(name="Stream title", value=info.get("title"), inline=False)
        e.add_field(name="Begin:", value=str(event.begin), inline=False)
        e.add_field(name="Duration: ", value=str(event.duration), inline=False)
        e.add_field(name="Link", value=info.get("url"), inline=False)
        e.set_image(url=info.get("thumbnail") or e.Empty)
        return e

    async def call(self, action, channel=None):
        
        action = action.lower()
        if not action in ("add", "remove", "next"):
            await self.respond("Action must be either 'add', 'remove' or 'next'.", True)

        db = self.db.getServer("global")
        db.createTableIfNotExists("vtuber_notification_channels", {"channel_id": "int"})

        if action == "add":
            if channel is None:
                await self.respond("Must specify channel ID.", True)
                return
            ds = db.createDatasetIfNotExists("vtuber_notification_channels", {"channel_id": channel.id})
            ds.update()
            await self.respond("Successfully added channel %s." % channel.name)

        elif action == "remove":
            if channel is None:
                await self.respond("Must specify channel ID.", True)
                return
            for ds in db.enumerateDatasets("vtuber_notification_channels"):
                if ds.getValue("channel_id") == channel.id:
                    ds.delete()
            await self.respond("Successfully removed channel %s." % channel.name)

        elif action == "next":
            earliest = None
            now = arrow.utcnow()
            for event in self._schedule.events:
                if event.begin < now:
                    continue
                if earliest is None or event.begin < earliest.begin:
                    earliest = event
            if earliest is None:
                await self.respond("There are no further scheduled events for today.")
            else:
                info = await self._get_info(earliest)
                await self.respond("Next up on the schedule:")
                await self.embed(await self._create_embed(earliest, info))