import asyncio
from urllib import request

import discord
from bs4 import BeautifulSoup as BS

from cmdsys import *
from version import S_TITLE_VERSION

import imagelib

class WeatherCommand(Command):

    STATION_ID = 10046
    URL = "https://www.wetteronline.de/wetter-aktuell/kiel?frequency=hourly&iid=%i"
    USER_AGENT = S_TITLE_VERSION

    def setup(self):

        self.name = "weather"
        self.desc = "Prints the weather report for Fredis house."

        self.ENABLE_GRAPH = True
        if not imagelib.init():
            self.logger.warn("Unable to load imagelib module, graph view will not be supported.")
            self.ENABLE_GRAPH = False

        if self.ENABLE_GRAPH:
            self.addArgument(Argument("style", CmdTypes.STR, True))
            graph_desc = """You can choose to have the report displayed as a table embed or a multigraph view.
Do this by specifying `embed` or `graph` as the first argument respectively.
If ommitted, this defaults to `embed`."""
            self.desc += "\n\n" + graph_desc

    def _text2percent(self, text):

        return int(text[:-1])/100

    def _dist2m(self, dist):

        if dist == "-":
            return -1

        if dist.startswith(">") or dist.startswith("<"):
            dist = dist[1:]

        v, d = dist.split(" ")
        if d == "km":
            m = 1000
        else:
            m = 1
        return float(v)*m

    def _intSafe(self, s):

        try:
            return int(s)
        except:
            return -1

    def _translateWindDir(self, dir):

        if dir == "O":
            return "E"
        elif dir == "NO":
            return "NE"
        elif dir == "SO":
            return "SE"
        return dir

    def _getTable(self, element):

        hourly = element.find("table", {"class": "hourly"})
        table = hourly.find("tbody")
        return table.find_all("tr")

    def _getTableForCategory(self, e, category):

        cat = e.find("div", {"id": category})
        return self._getTable(cat)

    async def _processData(self, data):

        loop = asyncio.get_event_loop()
        self.logger.debug("Parsing HTML...")
        html = await loop.run_in_executor(None, BS, data)

        #First, get the table container
        showcase = html.find("div", {"id": "showcase"})

        table_data = {}

        self.logger.debug("Processing temperature data...")
        temp = []
        for event in self._getTableForCategory(showcase, "temperature"):
            e = event.find_all("td")
            temp.append({"time": e[0].text,
                         "value": e[1].text,
                         "label": e[2].text})

        table_data["temperature"] = temp

        self.logger.debug("Processing humidity data...")
        humid = []
        for event in self._getTableForCategory(showcase, "humidity"):
            e = event.find_all("td")
            humid.append({"time": e[0].text,
                          "value": self._text2percent(e[1].text),
                          "dist": self._dist2m(e[2].text)})

        table_data["humidity"] = humid

        self.logger.debug("Processing precipitation data...")
        prec = []
        for event in self._getTableForCategory(showcase, "precipitation"):
            e = event.find_all("td")
            prec.append({"time": e[0].text,
                         "value": e[1].text,
                         "label": e[2].text})

        table_data["precipitation"] = prec

        self.logger.debug("Processing wind data...")
        wind = []
        for event in self._getTableForCategory(showcase, "wind"):
            e = event.find_all("td")
            wind.append({"time": e[0].text,
                         "average": self._intSafe(e[1].text),
                         "top": self._intSafe(e[3].text),
                         "direction": e[4].text,
                         "sector": self._translateWindDir(e[5].text)})

        table_data["wind"] = wind

        self.logger.debug("Processing cloud data...")
        clouds = []
        for event in self._getTableForCategory(showcase, "clouds"):
            e = event.find_all("td")
            clouds.append({"time": e[0].text,
                           "value": e[1].text}) #for some reason, the hourly reports here use a different format?

        table_data["clouds"] = clouds

        self.logger.debug("Processing air pressure data...")
        pressure = []
        for event in self._getTableForCategory(showcase, "pressure"):
            e = event.find_all("td")
            pressure.append({"time": e[0].text,
                             "value": self._intSafe(e[1].text)})

        table_data["pressure"] = pressure

        self.logger.debug("Processing snow data...")
        snow = []
        for event in self._getTableForCategory(showcase, "snow"):
            e = event.find_all("td")
            snow.append({"time": e[0].text,
                         "height": self._intSafe(e[1].text)})

        table_data["snow"] = snow

        return table_data

    async def _getData(self):

        url = self.URL % self.STATION_ID
        req = request.Request(url, headers={"user-agent": self.USER_AGENT}, method="GET")
        loop = asyncio.get_event_loop()
        self.logger.debug("Fetching weather report...")
        res = await loop.run_in_executor(None, request.urlopen, req)
        return res

    def _createGraph(self, width, height, data, n=0, bgcolor=(0, 0, 0), fgcolor=(255, 0, 0), line_width=2):

        """
        Create a graph view of the specified datapoints.

        width and height specify the width and height of the resulting surface.
        data should be a list of integers or floats specifying datapoints. Negative values will be ignored.
        If n is greater 0, it specifies the exact amount of datapoints that should be drawn. The graph will be
            padded or truncated to fit.
        """

        print(len(data))

        img = imagelib.Image(width, height, "graph")
        surf = img.getSurface()
        surf.fill(bgcolor)

        #calculate range

        p_max = max(data)
        p_min = max(0, min(data))

        #if p_max == p_min: #make sure p_max - p_min is never 0
        p_max += 1
        p_min -= 1

        p_max_ad = p_max - p_min

        #transform data to graph space

        n_points = []
        for point in data:
            n_points.append(height - ((point - p_min) / p_max_ad) * height)

        #pad / truncate graph

        if n > 0:
            l = len(n_points)
            if l > n:
                n_points = n_points[:n]
            elif l < n:
                n_points.extend([-1] * n - l)

        n_points.reverse() #data is supplied in newest-first, which isn't normal reading order (oldest-first)

        #Draw graph

        l = len(n_points)
        step = width/(l-1)
        for i in range(l-1):

            a = (int(step*i), int(n_points[i]))
            b = (int(step*(i+1)), int(n_points[i+1]))

            if not (a[1] >= 0 and b[1] >= 0):
                continue #Don't draw lines between points that have no valid value

            imagelib.pygame.draw.line(surf, fgcolor, a, b, line_width)

        img.max = int(p_max)
        img.min = int(p_min)

        return img

    def makeGraphView(self, table):

        GRAPH_SIZE = (150, 50)
        GRAPH_PADDING = 15
        GRAPH_COUNT = 4

        POINT_COUNT = 11

        width = GRAPH_SIZE[0] + 100
        height = (GRAPH_SIZE[1] + GRAPH_PADDING * 2) * 4

        surf = imagelib.pygame.Surface((width, height))
        surf = imagelib.convert(surf)
        surf.fill((54, 57, 63))
        img = imagelib.Image.fromSurface(surf, "weatherReport.png")

        n = 0
        temp = [float(x["value"].split(" ")[0][:-1]) for x in table["temperature"]]
        i = self._createGraph(GRAPH_SIZE[0], GRAPH_SIZE[1], temp, POINT_COUNT, fgcolor=(100, 100, 255))
        img.blit(i, (GRAPH_PADDING, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING))
        img.writeText((2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n, width-4, GRAPH_PADDING), "Temperature (C)", (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING, 100-2, GRAPH_PADDING), str(i.max), (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_SIZE[1], 100-2, GRAPH_PADDING), str(i.min), (200, 200, 200), "Consolas")

        n += 1
        hum = [x["value"]*100 for x in table["humidity"]] #convert to %
        i = self._createGraph(GRAPH_SIZE[0], GRAPH_SIZE[1], hum, POINT_COUNT, fgcolor=(255, 200, 0))
        img.blit(i, (GRAPH_PADDING, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING))
        img.writeText((2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n, width-4, GRAPH_PADDING), "Humidity (Relative %)", (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING, 100-2, GRAPH_PADDING), str(i.max), (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_SIZE[1], 100-2, GRAPH_PADDING), str(i.min), (200, 200, 200), "Consolas")

        n += 1
        wind = [x["average"] for x in table["wind"]]
        i = self._createGraph(GRAPH_SIZE[0], GRAPH_SIZE[1], wind, POINT_COUNT, fgcolor=(255, 0, 240))
        img.blit(i, (GRAPH_PADDING, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING))
        img.writeText((2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n, width-4, GRAPH_PADDING), "Wind (km/h)", (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING, 100-2, GRAPH_PADDING), str(i.max), (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_SIZE[1], 100-2, GRAPH_PADDING), str(i.min), (200, 200, 200), "Consolas")

        n += 1
        pres = [x["value"] for x in table["pressure"]]
        i = self._createGraph(GRAPH_SIZE[0], GRAPH_SIZE[1], pres, POINT_COUNT, fgcolor=(70, 255, 70))
        img.blit(i, (GRAPH_PADDING, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING))
        img.writeText((2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n, width-4, GRAPH_PADDING), "Air Pressure (hPa)", (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_PADDING, 100-2, GRAPH_PADDING), str(i.max), (200, 200, 200), "Consolas")
        img.writeText((GRAPH_SIZE[0]+2, (GRAPH_PADDING*2+GRAPH_SIZE[1]) * n + GRAPH_SIZE[1], 100-2, GRAPH_PADDING), str(i.min), (200, 200, 200), "Consolas")

        return img

    async def call(self, style="embed", **kwargs):

        if not style in ("embed", "graph"):
            await self.respond("style must be either 'embed' or 'graph'.", True)
            return

        await self.respond("Working on it...")

        try:
            data = await self._getData()
        except Exception as e:
            await self.respond("Unabled to fetch weather report: %s" % str(e), True)
            return

        try:
            table = await self._processData(data)
        except Exception as e:
            await self.respond("Unabled to process weather report: %s" % str(e), True)
            return

        if style == "embed":

            inline=False

            e = discord.Embed(title="Weather Report :partly_sunny:", description="", color=0x4040FF)
            e.add_field(name="Temperature", value=table["temperature"][0]["value"], inline=inline)
            e.add_field(name="Humidity (relative)", value=str(table["humidity"][0]["value"]), inline=inline)
            #e.add_field(name="Precipitation", value=table["precipitation"][0]["value"], inline=inline)
            wind = table["wind"][0]
            text = "Average: %i | Top: %i | Direction %s %s" % (wind["average"], wind["top"], wind["direction"], wind["sector"])
            e.add_field(name="Wind (km/h)", value=text, inline=inline)
            e.add_field(name="Pressure (hPa)", value=str(table["pressure"][0]["value"]), inline=inline)
            e.add_field(name="Snow height (cm)", value=str(table["snow"][0]["height"]), inline=inline)

            await self.embed(e)

        else:

            graph = self.makeGraphView(table)
            await self.client.send_file(self.msg.channel, fp=graph, filename=graph.name, content="Weather Report :partly_sunny:")