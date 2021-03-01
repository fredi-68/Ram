import discord
import chatutils
from cmdsys import *

from core_models import PinReactionSettings, PinChannel

class CmdPin(Command):

    #Subcommands
    class PinConfig(Command):

        class PinConfigEmote(Command):

            def setup(self):

                self.name = "enable"
                self.desc = "Configure the emote used for reaction based pinning."

                self.addArgument(IntArgument("count", False))
                self.addArgument(StringArgument("emote", True))
                self.addArgument(BoolArgument("needs_mod", True))

            async def call(self, count, emote="", needs_mod=False):

                db = self.db.get_db(self.msg.guild.id) #get the server database
                m = db.new(PinReactionSettings)
                m.count = count
                m.emote = emote
                m.needs_mod = needs_mod
                m.save()

                await self.respond("Enabled reaction based pinning.")

        def setup(self):

            self.name = "reaction"
            self.desc = "Configure the reaction based pin interface. Action should be either 'enable' or 'disable'."

            self.addArgument(StringArgument("action", False))
            self.addSubcommand(self.PinConfigEmote())

        async def call(self, action):

            if action.lower() != "disable":
                await self.respond("action must be either 'enable' or 'disable'.", True)
                return

            db = self.db.get_db(self.msg.guild.id) #get the server database
            db.query(PinReactionSettings).delete()

            await self.respond("Disabled reaction based pinning.")

    def setup(self):

        self.name = "pin"
        self.desc = "'Pins' a message to a channel by copying it to a predefined pin channel."
        self.permissions.administrator = True
        self.addArgument(MessageArgument("message"))
        self.allowConsole = False

        self.addSubcommand(self.PinConfig())

        #self.initLib()

    def initLib(self):

        global imagelib

        try:
            import imagelib
            imagelib.init(True)
        except:
            self.logger.exception("ImageLib couldn't be initialized, this command will not be available.")
            self.allowChat = False

    async def call(self, message, **kwargs):

        db = self.db.get_db_by_message(self.msg)
        q = db.query(PinChannel)

        if len(q) < 1: #we don't have any pin channels for this server
            await self.respond("Pins are not setup for this server.", True)
            return

        msg = message
        cmd = self.msg
        pin_icon = self.config.getElementText("bot.icons.pin")

        title = "Pinned Message " + pin_icon #Embed title #TODO: Work out how those fancy fields work an use those instead of our clunky implementation.

        desc = "MESSAGE PINNED BY " + chatutils.mdBold(cmd.author.name) + " AT " + chatutils.mdBold(cmd.created_at.strftime("%c")) + \
        ":\n-------------------------------------\nORIGINAL MESSAGE BY " + chatutils.mdBold(msg.author.name) + " IN " + \
        chatutils.mdBold(msg.channel.name) + " AT " + chatutils.mdBold(msg.created_at.strftime("%c")) + "\n\n"
    
        desc += msg.content+"\n" #pinned message
        image = None
        for i in msg.attachments: #process file attachments (currently adding them as links) TODO: Make this dynamically add images and videos to the respective Embed fields
            for j in ["png", "jpg", "jpeg", "gif"]: #there HAS to be a better way to do this... *sigh*
                if i["url"].endswith("." + j):
                    image = i["url"]
            desc += "\n"+str(i["url"])

        e = discord.Embed(title=title, description=desc, color=discord.Color.magenta()) #make pins show up as Embeds
        if image:
            e.set_image(url=image)

        for i in q:
            dch = self.msg.guild.get_channel(i.channel_id)
            await dch.send(embed=e)