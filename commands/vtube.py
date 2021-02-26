import discord
import arrow
import asyncio
import datetime
from urllib import request

from youtube_dl import YoutubeDL, DownloadError
from youtube_dl.extractor.youtube import YoutubeIE, compat_parse_qs
from ics import Calendar

from cmdsys import *

from database import Model, IntegerField, PKConstraint, AIConstraint

class VtuberChannel(Model):

    channel_id = IntegerField(constraints=[PKConstraint(), AIConstraint()])

class VTube(Command):

    """
    Holodule notification integration.

    This command provides integration with the Holodule Hololife ICS Schedule project.
    More information at https://github.com/sarisia/holodule-ics

    This command takes many configuration options.
    ICS_URL specifies the target ICS file to track.
    Various timing adjustments are possible through use of the SCHEDULE_* variables.
    """

    #YTDL Options
    YOUTUBE_DL_OPTIONS = {
        "format": "webm[abr>0]/bestaudio/best",
        "prefer_ffmpeg": True,
        #"ignoreerrors": True,
        "nocheckcertificate": True #nocheckcertificate is necessary for this to work on the AWS server for some reason...
        }
    YOUTUBE_DL_EXTRACT_OPTIONS = {
        "download": False
        }

    #Scheduler timings
    SCHEDULE_SLEEP_INTERVAL = 60 #time the scheduler sleeps between task checks, in seconds
    SCHEDULE_UPDATE_FREQUENCY = 2 #times the schedule is updated, per hour
    SCHEDULE_CHECK_FREQUENCY = 60 #times the schedule is checked for active events, per hour
    SCHEDULE_REEVALUATION_INTERVAL = 300 #seconds to wait between notification reevaluation attempts
    SCHEDULE_FORWARD_SHIFT = 0 #lookahead delay when checking for active events, in seconds

    ICS_URIS = [
        "https://sarisia.cc/holodule-ics/holodule-english.ics",
        "https://sarisia.cc/holodule-ics/holodule-indonesia.ics"
        ]
    #ICS_URI = "https://sarisia.cc/holodule-ics/holodule-all.ics"

    def setup(self):

        self.name = "holodule"
        self.desc = "Manage Hololive livestream notifications."
        self.permissions.administrator = True
        self.allowDelimiters = False

        self.addArgument(StringArgument("action"))
        self.addArgument(ChannelArgument("channel", True))

        self._schedule = None
        self._task_runner_handle = self.loop.create_task(self._task_runner())
        cleanUpRegister(self._cleanup)

        environment.database.register_model(VtuberChannel)

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

        self.logger.info("Updating schedule using %i sources..." % len(self.ICS_URIS))

        self._schedule = Calendar()

        for uri in self.ICS_URIS:
            req = request.Request(uri)
            res = await self.loop.run_in_executor(None, lambda: request.urlopen(req))
            self._schedule.events.update(Calendar(res.read().decode("utf-8")).events)

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
        db = self.client.db.get_db("global")
        
        info = await self._get_info(event)
        for ds in db.query(VtuberChannel):
            try:
                ch = await self.client.fetch_channel(ds.channel_id)
                mention_role = None
                for role in ch.guild.roles:
                    if role.name == "vtub":
                        mention_role = role
                        break
                if msg is None:
                    text = "%s, %s is streaming" % ((mention_role.mention if mention_role is not None else ""), info["streamer"])
                    msg = await ch.send(text, embed=await self._create_embed(event, info))
                else:
                    await msg.edit(embed=await self._create_embed(event, info))
            except:
                self.logger.exception("Exception happened in notification dispatcher: ")

        if not info.get("is_live"):

            if arrow.utcnow() > event.end:
                self.logger.error("Event %s has ended, but never went live. Cancelling reevaluation tasks." % repr(event))
                return

            delay = self.SCHEDULE_REEVALUATION_INTERVAL
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

        e = discord.Embed(url=info.get("url"))
        e.title = "%s %s!" % (info.get("streamer"), info.get("live_status"))
        e.add_field(name="Stream title", value=info.get("title"), inline=False)
        e.add_field(name="Begin:", value=event.begin.format("HH:mm:ss ZZZ") + " (" + event.begin.humanize() + ")", inline=False)
        e.add_field(name="Duration: ", value=str(event.duration), inline=False)
        #e.add_field(name="Link", value=info.get("url"), inline=False)
        e.set_image(url=info.get("thumbnail") or e.Empty)
        return e

    async def call(self, action, channel=None):
        
        action = action.lower()
        if not action in ("add", "remove", "next"):
            await self.respond("Action must be either 'add', 'remove' or 'next'.", True)

        db = self.db.get_db("global")

        if action == "add":
            if channel is None:
                await self.respond("Must specify channel ID.", True)
                return
            m = db.new(VtuberChannel)
            m.channel_id = channel.id
            m.save()
            await self.respond("Successfully added channel %s." % channel.name)

        elif action == "remove":
            if channel is None:
                await self.respond("Must specify channel ID.", True)
                return
            db.query(VtuberChannel).filter(channel_id=channel.id).delete()
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