import asyncio
import json
import re

import discord
import arrow
from arrow import Arrow

from cmdsys import *

from database import Model, IntegerField, TextField, FloatField

class MalformedPatternException(BaseException):

    pass

#CONDITION FACTORIES

_RANGE_RE = re.compile("^([0-9]+)([smhd])$")
_RANGE_FACTORS = {
    "s": 1,
    "m": 60,
    "h": 60*60,
    "d": 60*60*24
}
def _convert_range(t):

    match = _RANGE_RE.match(t)
    t, s = match.groups()

    return int(t) * _RANGE_FACTORS[s]

class Condition():

    def __init__(self, expr):

        self.expr = expr
        self.parse()

    def parse(self):

        pass

    def check(self, last):

        return True

    def __call__(self, job, msg):

        return True

class _Handle_Before(Condition):

    """
    Checks if a message is older than a specific amount of time.
    """

    def parse(self):

        self.time = _convert_range(self.expr)

    def __call__(self, job, msg):

        return arrow.get(msg.created_at) < Arrow.now().shift(seconds=-self.time)

class _Handle_When(Condition):

    """
    Allow control of when a purge is executed.
    """

    def parse(self):

        self.time = _convert_range(self.expr)

    def check(self, last):

        return last.shift(seconds=self.time) < Arrow.now()

class AutoPurgeJob(Model):

    channel_id = IntegerField()
    pattern = TextField()
    last = FloatArgument(default=0)

class Job():

    TABLE_NAME = "auto_purge_jobs"
    CONDITION_HANDLES = {
        "before": _Handle_Before,
        "when": _Handle_When
    }

    def __init__(self, client: "ProtosBot", channel: "TextChannel", pattern: str, last: Arrow = Arrow.now()):

        """
        Create a new job.

        client is the bot instance.
        channel is the text channel this job should run in.
        pattern is the pattern of checks to execute against messages.
        last is the last time this job was executed.
        """

        self.client = client
        self.channel = channel
        self.pattern = json.loads(pattern)
        self.last = last

        self._conditions = set()
        self._parse_pattern(self.pattern)

        if not self._conditions:
            raise MalformedPatternException("Must specify at least one condition.")

    @classmethod
    async def from_dataset(cls, client: "ProtosBot", ds: "DatasetHandle") -> "Job":

        """
        Create a new job from a dataset.
        """

        channel = await client.fetch_channel(ds.getValue("channel"))

        return Job(client, channel, ds.getValue("pattern"), Arrow.fromtimestamp(ds.getValue("last")))

    def to_dataset(self, db: "DatabaseHandle") -> "DatasetHandle":

        """
        Save this job to the database.
        """

        channel = self.channel.id
        pattern = json.dumps(self.pattern)
        last = self.last.timestamp

        ds = db.createDatasetIfNotExists(self.TABLE_NAME, {"channel": channel, "pattern": pattern})
        ds.setValue("last", last)
        ds.update()

        return ds

    def _parse_pattern(self, pattern: dict):

        for t, expr in pattern.items():
            if not t in self.CONDITION_HANDLES:
                raise MalformedPatternException("Condition type %s does not have a registered handle." % t)
            try:
                c = self.CONDITION_HANDLES[t](expr)
            except Exception as e:
                raise MalformedPatternException("Invalid pattern %s." % expr) from e
            self._conditions.add(c)

    def check(self) -> bool:

        """
        Perform check for 
        """

        for condition in self._conditions:
            if not condition.check(self.last):
                return False

        return True

    async def __call__(self) -> int:

        def check(msg):
            for condition in self._conditions:
                if not condition(self, msg):
                    return False
            return True

        c = await self.channel.purge(check=check)

        self.last = Arrow.now()

        return len(c)

class AutoPurge(Command):

    JOB_CHECK_INTERVAL = 60 #how often to check active jobs, in seconds

    class AddJob(Command):

        def __init__(self, parent):

            super().__init__()
            self.parent = parent

        def setup(self):

            self.name = "add"
            self.desc = "Add a new job."
            self.permissions.administrator = True
            self.addArgument(ChannelArgument("channel"))
            self.addArgument(StringArgument("expr"))

        async def call(self, channel, expr):

            try:
                job = Job(self.client, channel, expr)
            except MalformedPatternException as e:
                await self.respond("Could not create job: %s" % str(e), True)
                return

            db = self.db.getServer("global")
            db.createTableIfNotExists(Job.TABLE_NAME, {"channel": "int", "pattern": "text", "last": "int"})
            job.to_dataset(db)
            self.parent.create_job(job)            

            await self.respond("Successfully created job!")

    def setup(self):

        self.name = "autopurge"
        self.desc = "Purge messages automatically based on one or multiple constraints."
        self.permissions.administrator = True

        self._jobs = set()

        self.addArgument(Argument("action"))
        self.addSubcommand(self.AddJob(self))

        self._dispatcher_task = self.loop.create_task(self._job_dispatcher())
        cleanUpRegister(self._cleanup)

    async def _cleanup(self):

        self._dispatcher_task.cancel()

    async def _job_dispatcher(self):

        while self.loop.is_running():
            #check jobs
            for job in self._jobs:
                try:
                    if job.check():
                        self.logger.debug("Condition met for job %s, executing purge task..." % str(job))
                        try:
                            c = await job()
                        except Exception as e:
                            await self.log("Failed to execute job: %s" % str(e))
                            continue
                        if c > 0:
                            await self.log("AutoPurge deleted %i message(s) from channel %s.", c, str(job.channel))
                except Exception as e:
                    print(e)

            await asyncio.sleep(self.JOB_CHECK_INTERVAL)

    def create_job(self, job):

        self._jobs.add(job)

    async def call(self, action):
        
        return