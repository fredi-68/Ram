import discord
from cmdsys import *
import chatutils

class DatasetWrapper():

    def __init__(self, dataset):

        self.dataset = dataset

    def __lt__(self, other):

        return self.dataset.getValue("points") < other.dataset.getValue("points")

class MyCommand(Command):

    def setup(self):

        self.name = "privilege"
        self.desc = "See how privileged you are. Optional target argument can be a user or 'ranking' to show the leaderboard"
        self.aliases.append("myPrivilege")
        self.allowConsole = False
        self.addArgument(Argument("target", CmdTypes.STR, True))

    async def call(self, target="", **kwargs):

        db = self.db.getDatabaseByMessage(self.msg)
        db.createTableIfNotExists("privilegePoints", {"user": "int", "points": "int"}, True)

        if target in ("ranking", "leaderboard", "board", "scoreboard"):

            dslist = db.enumerateDatasets("privilegePoints")

            rets = ":pp: Privilege Points Leaderboard :pp:\n\n"

            wrapperList = list(map(DatasetWrapper, dslist))
            wrapperList.sort()
            for i in wrapperList:
                try:
                    rets += self.msg.guild.get_member(i.dataset.getValue("user")).name + ": " + str(i.dataset.getValue("points")) + "\n"
                except AttributeError:
                    #this happens when we try to display a user who is not in this server, since the value returned by get_member() is None in this case.
                    pass

            await self.respond(rets, True)
            return

        if not target:
            target = self.msg.author

        else:

            t = chatutils.getMention(target)

            try:
                target = self.msg.guild.get_member(t if t else target)
            except:
                await self.respond("Illegal value for target: "+target, True)
                return

        ds = db.createDatasetIfNotExists("privilegePoints", {"user": target.id}) #create a new entry for the user or get the one we are already using

        await self.respond("User "+str(target.name)+" has accumulated "+str(ds.getValue("points"))+" :pp:") #Execute search query for our dataset and get the points value