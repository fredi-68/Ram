import json
import os

import discord
from cmdsys import *

BASE_PATH = "chat/memes/genTemplates"

class MyCommand(Command):

    def setup(self):

        self.name = "meme"
        self.desc = "Meme generator."
        self.allowConsole = False
        self.addArgument(Argument("template", CmdTypes.STR))
        self.addArgument(Argument("line1", CmdTypes.STR))
        self.addArgument(Argument("line2", CmdTypes.STR, True))

        self.initLib()

    def initLib(self):

        global imagelib

        try:
            import imagelib
            imagelib.init(True)
        except:
            self.logger.exception("ImageLib couldn't be initialized, this command will not be available.")
            self.allowChat = False

    async def getHelp(self):

        #We override this to update the description each time we query the help page to update available templates
        templates = self.loadTemplates(BASE_PATH)

        self.desc = "Meme generator.\n\nAvailable templates:\n\n"
        if len(templates) < 1:
            self.desc += "None\n"
        else:
            for i in templates:
                self.desc += i["name"] + "\n"

        return await Command.getHelp(self)

    def loadTemplates(self, path):

        """
        Load meme templates and return them as a list.

        To create your own meme templates, put them in the folder located at
        chat/memes/genTemplates
        There are a few examples to get you started. A template is stored as a JSON file and
        needs at least one line definition and an associated image.
        The bot will log an error if a template failed to load so you can figure out what went wrong more easily.
        """

        self.logger.debug("Refreshing templates...")
        files = os.listdir(path)
        templates = []
        for i in files:
            p = os.path.join(path, i)
            if os.path.isfile(p) and p.endswith("json"):
                self.logger.debug("Loading template %s..." % p)
                try:
                    with open(p, "r") as f:
                        template = json.load(f)
                        templates.append(template)
                except (OSError, json.JSONDecodeError):
                    self.logger.exception("Failed to load template %s: " % p)

        return templates

    async def call(self, template="", line1="", line2="", **kwargs):

        if not (line1 or line2):
            await self.respond("Must specify at least one line of text.", True)
            return

        lines = [line1, line2]
        templates = self.loadTemplates(BASE_PATH) #reload templates each time the command is invoked. May have to change this if performance suffers (or thread it)

        for i in templates:
            if i["name"] == template:

                self.logger.debug("Loading image...")
                img = imagelib.loadImage(os.path.join(BASE_PATH, i["source"]))
                self.logger.debug("Rendering...")
                for j in range(len(i["lines"])):
                    line = i["lines"][j] #get our line template
                    if j >= len(lines): #abort if we ran out of user input
                        break
                    text = lines[j] #get our current text line
                    img.writeText((line["x"], line["y"], line["width"], line["height"]), text, line["color"], None, draw_shadows=line.get("draw_shadow", 0), shadow_color=line.get("shadow_color", (0, 0, 0)))

                self.logger.debug("Uploading...")
                await self.client.send_file(self.msg.channel, fp=img, filename=img.name, content="Here is your meme: ")
                return

        await self.respond("That template doesn't exist.", True)
        return
