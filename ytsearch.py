#Discord ProtOS Bot
#
#Author: fredi_68
#
#Music Search Engines
#Currently available search engines:
#   YouTube
#   SoundCloud

import logging
import json
from urllib import request

logger = logging.getLogger("ytsearch")
HAS_SOUNDCLOUD = True
try:
    import soundcloud
except ImportError:
    logger.warn("Unable to import soundcloud module, soundcloud search engine will not be available.")
    HAS_SOUNDCLOUD = False

import version

class Search():

    """
    Abstract base class for search engines.

    This class specifies an interface for music search egines.
    It also provides some shared functionality and object instances.
    """

    logger = logging.getLogger("GenericSearchEngine")

    def __init__(self):

        """
        Initialize the search engine.

        You may change this constructor to fit your implementations needs,
        it is not part of the interface definition.
        """

        self.serviceName = "Generic"

    def search(self, query, maxresults=10, lang="en", **opt):

        """
        Query the search engine and return the results.

        This method takes the query string and returns a dictionary of url:title mappings.
        The length of the returned dictionary does not have to be maxresult, but may not be
        larger. It may be empty.
        lang is a ISO 639-1 two-letter language code and should be used to narrow the search results by
        language, if applicable.
        A search engine may add support for additional options, these should be included as additional
        keyword only arguments. All keyword arguments are considered optional.
        """

        return {}

class YouTubeSearch(Search):

    def __init__(self, token):

        """
        Create a new YouTubeSearch instance.
        token should be a valid YouTube Data API key.
        """

        Search.__init__(self)

        self.token = token
        self.serviceName = "YouTube"

    def search(self, query, maxresults = 10, lang = 'en', **opt):

        """
        Searches YouTube for videos using the given query.
        Returns a dict of url: title pairs pointing to videos.

        If maxresults is given, it should be greater 0 and specifies the maximum amount of
        video urls returned. The resulting list may be shorter, or empty.
        If lang is given, it should be an ISO 639-1 two-letter language code, or any other
        language identifier recognized by the YouTube data API.

        For more information, please refer to https://developers.google.com/youtube/v3/docs/search/list
        Most of the parameters of this method are directly passed into the url
        """

        self.logger.info("Running YouTube search for query %s...", query)

        #Added some additional parameters here to ensure only videos come through (and English is preferred as the language)
        url = "https://www.googleapis.com/youtube/v3/search?q=%s&maxResults=%i&part=snippet&key=%s&relevanceLanguage=%s&type=video" % (query.replace(" ", "+"), maxresults, self.token, lang)
        self.logger.debug("URL is %s" % url)
        req = request.Request(url)
        req.add_header("User-Agent", version.S_TITLE_VERSION)
        req.add_header("Accept-Language", "en-US,en")
        res = request.urlopen(req)
        self.logger.debug("Server returned code %i: %s" % (res.code, res.msg))
        self.logger.debug("Examining response...")
        
        data = json.loads(res.read())

        #We want to extract the video ID from the JSON data to pass it into youtube_dl later
        urls = {}
        for i in data["items"]:
            try:
                urls["https://www.youtube.com/watch?v=%s" % i["id"]["videoId"]] = i["snippet"]["title"]
            except KeyError: #If for some reason an entry in our response wasn't a video, this will make sure that we don't crash
                pass

        return urls

class SoundCloudSearch(Search):

    def __init__(self, token):

        """
        Create a new SoundCloudSearch instance.
        token should be a valid SoundCloud Client ID.
        """

        Search.__init__(self)

        self.token = token
        if HAS_SOUNDCLOUD:
            self.client = soundcloud.Client(client_id=token)
        else:
            self.client = None
        self.serviceName = "SoundCloud"

    def search(self, query, maxresults=10, lang='en', **opt):

        """
        Searches SoundCloud for tracks using the given query.
        Returns a dict of url: title pairs pointing to tracks.

        If maxresults is given, it should be greater 0 and specifies the maximum amount of
        urls returned. The resulting list may be shorter, or empty.
        The lang option is not implemented by this search engine and will be ignored.

        A user may specify additional search terms by adding keyword arguments.
        These will be inserted into the query after the general search options.

        For more information, please refer to https://developers.soundcloud.com/docs/api/reference#tracks
        Most of the parameters of this method are directly passed into the url
        """
        
        if not HAS_SOUNDCLOUD:
            return {"Library unavailable": "This search engine cannot function properly, because the soundcloud package isn't installed on this machine. Please contact the bot owner if you believe this is an error."}

        tracks = self.client.get("/tracks", q=query, limit=maxresults, **opt)

        urls = {}
        for track in tracks:
            urls[track.permalink_url] = track.title

        return urls
