import urllib
import asyncio
import csv
import shlex

import discord

from cmdsys import *
from version import S_TITLE_VERSION

class Row():

    def __init__(self, order, title, url, notes, featuring, category):

        self.order = order
        self.title = title
        self.url = url
        self.notes = notes
        self.featuring = list(map(str.strip, featuring.split(",")))
        self.category = category

class SearchPrivateVideos(Command):

    DOCUMENT_ID = "1Bi0mg9aqWMFhnaNCPuPcTAqO_xqqfArSiGoJAdWUbCk"

    def setup(self):

        self.name = "unlisted"
        self.desc = """Search for videos in fredi_68's List of Unlisted Videos Google Docs sheet.

Enter search parameters using -<command> <argument> formatting. The following parameters are supported:
    -title - searches for a particular text sequence in video titles
    -notes - searches for a particular text sequence in notes
    -featuring - searches for a specific person that was featured in the video
    -category - only search in a specific category

Arguments can be escaped using quotes. Parameters can be used more than once to match multiple sequences."""

        self.addArgument(StringArgument("query"))

    async def getSheet(self, documentID):

        """
        Downloads the Google Sheet as a CSV file and returns a string containing the data
        """

        self.logger.info("Downloading video list...")
        url = "https://docs.google.com/spreadsheets/d/%s/export?format=csv&id=%s&gid=0" % (documentID, documentID)
        req = urllib.request.Request(url, headers={"User-Agent": S_TITLE_VERSION, "Accept-Encoding": "utf-8", "Accept-Language": "en"})
        loop = asyncio.get_event_loop()
        #make sure the process doesn't block
        res = await loop.run_in_executor(None, urllib.request.urlopen, req)
        return res.read().decode(encoding="utf-8")

    def parseSheet(self, data):

        """
        Parses a string of CSV data into a list of ROW_TUPLE instances representing
        video metadata entries.
        """

        self.logger.info("Parsing CSV...")
        reader = csv.reader(data.split("\n"))
        #convert the output from csv.reader into a more usable format
        rows = []
        for row in reader:
            rows.append(Row(*row))
        return rows[2:]

    async def call(self, query):
        
        table = self.parseSheet(await self.getSheet(self.DOCUMENT_ID))
        args = shlex.split(query)
        it = iter(args)
        self.logger.info("Filtering results...")
        try:
            for cmd in it:
                cmd = cmd.lower()
                m = next(it)
                #Okay, let it be known that list comprehension is fucking awesome
                if cmd == "-title":
                    table = [i for i in table if m in i.title]
                elif cmd == "-featuring":
                    table = [i for i in table if m in i.featuring]
                elif cmd == "-category":
                    table = [i for i in table if m == i.category]
                elif cmd == "-notes":
                    table = [i for i in table if m in i.notes]
                else:
                    await self.respond("Error: Unknown query parameter '%s'." % cmd, True)
                    return
        except StopIteration:
            await self.respond("Error: Unexpexted EOF encountered while parsing query string.", True)
            return

        if len(table) < 1:
            await self.respond("No entries matching your query were found.")
            return

        self.logger.info("Collecting final results...")
        e = discord.Embed(title="Search results :mag:", description="", color=discord.Color(0x6464FF))
        for r in table:
            e.add_field(name="%s. %s%s [%s]" % (r.order, r.title, ("" if not r.featuring else " ft. %s" % ", ".join(r.featuring)), r.category), value=r.url)
        
        await self.embed(e)