import discord
from cmdsys import *
from database import Model, IntegerField, PKConstraint, AIConstraint

class WeebModel(Model):

    user_id = IntegerField(constraints=[PKConstraint(), AIConstraint()])

class MakeWeeb(Command):

    def setup(self):

        self.name = "weeb"
        self.desc = "Show someone the way of the weeb."
        self.addArgument(MemberArgument("member"))
        self.ownerOnly = True
        self.hidden = True

        environment.database.register_model(WeebModel)

    async def call(self, member, **kwargs):

        if isinstance(member, str):
            try:
                member = self.msg.server.get_member(member)
            except:
                await self.respond("member must be a valid member ID", True)
                return
        elif not isinstance(member, discord.Member):
            await self.respond("member must be a valid member ID", True)
            return

        db = self.db.get_db("global") #use some global database
        if len(db.query(WeebModel).filter(user_id=member.id)) > 0:
            #user is already a weeb. FCKIN WEB LULZ
            await self.respond("That user is already a filthy weeb.", True)
            return
        #insert user into database
        m = db.new(WeebModel)
        m.user_id = member.id
        m.save()
        await self.respond("User "+member.name+" has been marked as a follower of The Power Of Anime. Congratulations "+member.mention+" , you are now a weeb.")

class _NeedWeeb(Command):

    LINK = ""

    async def call(self, **kwargs):

        db = self.db.get_db("global") #use some global database
        if len(db.query(WeebModel).filter(user_id=self.msg.author.id)) < 1:
            await self.respond("Only believers in the god of anime may use this command.", True)
            return

        #user is already a weeb
        await self.respond(self.LINK)

class HairBuns(_NeedWeeb):

    LINK = "https://gfycat.com/SecondaryPleasedIchthyosaurs"

    def setup(self):

        self.name = "buns"
        self.aliases.append("hair")
        self.desc = "Show appreciation for the wonderful things that are hair buns. WEEBS ONLY."
        self.allowConsole = False

class Culture(_NeedWeeb):

    LINK = "https://cdn.discordapp.com/attachments/328154495697682444/410061750436888576/aa6ddb3424502c39605e6859b5cc89d2dd737cdc62910218c801936adcf5434b.gif"

    def setup(self):

        self.name = "culture"
        self.desc = "Show that you are a cultured individual. WEEBS ONLY."
        self.allowConsole = False

class HMMMMMMMMMMM(_NeedWeeb):

    LINK = "https://uploads.disquscdn.com/images/88bdde16848bcc37c7f626390a0de9044c17ad93bba379664930a631caed1e55.gif"

    def setup(self):

        self.name = "hmm"
        self.desc = "HMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMmmmmmmmmmmmmmmm..."
        self.allowConsole = False
