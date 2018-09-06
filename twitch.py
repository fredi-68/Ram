#Discord ProtOS Bot
#
#Author: Jascha "fredi_68" Hirsekorn
#
#Twitch integration
#https://www.twitch.tv

from urllib import request
from http import server
import json
import webbrowser
import threading
import uuid
import logging

logger = logging.getLogger("Twitch")

CONFIG_PATH = "config/twitch.xml"

def getRamResponse(text, success=False):

    """
    Standard text for the HTTP server
    """

    try:
        f = open("twitchres/"+("responseSuccess" if success else "responseFailure")+".html", "r")
        lines = f.readlines()
        f.close()
    except:
        return "Hi! I'm Ram and this is my OAuth2 token reception server. <br />"+text #fall back to the old default message

    response = "".join(lines)
    return response.replace("this is where the message should be", "Hi! I'm Ram and this is my OAuth2 token reception server. <br />"+text)

def getJSONRequest(res):

    """
    Returns a dict equivalent of the json data contained in the urllib.response.Response object
    """

    return json.loads(res.read().decode("ASCII", "ignore"))

def getTwitchRequest(url, client):

    """
    Requests the ressource at the given location, providing authentication information from the client
    """

    headers = {"Accept":"application/vnd.twitchtv.v5+json"} #Use Twitch API v5
    if isinstance(client,TwitchClient):

        #Set token if we are logged in and client ID if we are not

        if client.token:
            headers["Authorization"] = "OAuth "+client.token
        elif client.id:
            headers["Client-ID"] = client.id
        else:
            return {} #twitch client wasn't initialized properly, send an empty dictionary
    else:
        raise ValueError("client must be of type TwitchClient")
    return getJSONRequest(request.urlopen(request.Request(url, headers=headers)))

def getUserID(user,client):

    """
    Returns the user ID for the given username
    """

    res = getTwitchRequest("https://api.twitch.tv/kraken/users?login="+user, client)
    return res["users"][0]["_id"]

def getChannelGame(channel,client):

    """
    Returns the game played on the given channel at the moment
    """

    res = getTwitchRequest("https://api.twitch.tv/kraken/channels/"+getUserID(channel, client), client)
    return res["game"]

class OAuthServer(server.HTTPServer):

    def __init__(self, address, callback):

        self.tokenCallback = callback
        server.HTTPServer.__init__(self, server_address=address, RequestHandlerClass=OAuthHandler)

    def handleToken(self, token, state):

        self.tokenCallback(token, state)

    def handle_error(req,cl_addr):

        return #we don't want random error messages to confuse the user (and shutting down the server does throw one because for some reason the webpage doesn't get sent properly)

class OAuthHandler(server.BaseHTTPRequestHandler):

    def do_GET(self):

        if not self.path.startswith("/oauth"):
            #certainly no valid request
            self.send_error(400, "Bad Request", getRamResponse("Seems like you are looking for something that isn't here. Best of luck finding it.", False))
            self.close_connection = True
            return
        
        code = None
        state = None

        for i in self.path.split("?", 1)[1].split("&"): #get list of query strings
            k, v = i.split("=", 1)
            if k == "code":
                code = v
            elif k == "state":
                state = v

        if not code:
            #again, not a valid request
            self.send_error(400, "Bad Request", getRamResponse("I couldn't find an access token in your response but I kind of need it to continue... ", False))
            self.close_connection = True
            return
        
        self.send_response(200,"OK, token validation in progress") #HTTP status response

        #Headers
        self.send_header("Content-type", "text/html; charset=UTF-8")
        response = getRamResponse("Your request has been processed successfully! I'll go ahead and save this token for you. See you on twitch.tv soon! :3", True)
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Content-Encoding", "UTF-8")

        self.end_headers()

        #Content
        self.wfile.write(response.encode(encoding="UTF-8"))

        self.close_connection = True
        self.server.handleToken(code, state)
        print("Closing server...")
        try:
            self.server.server_close()
        except OSError:
            pass #This happens because the underlying TCP server refuses to shutdown, so we have to force it to stop, which unfortunately leads to a nasty error.
            #Nothing we can do about this though...

        return

class TwitchClient():

    def __init__(self, cfg):

        """
        Wrapper around the twitch REST API
        This class represents one client connection to the twitch service.
        It features automatic token request using a local webserver and token caching.
        """

        self.id = None
        self.secret = None
        self.token = None
        self.ready = False

        self.config = cfg
        self.load()
        self.save()

    def checkToken(self, token=None):

        """
        Checks if the given token is valid
        """

        if token:
            self.token = token #set token if provided with one
        self.ready = False

        #make sure we have a token
        if not self.token:
            logger.info("No Twitch access token found, requesting a new one...")
            self.getToken()
            return

        #validate token
        try:
            res = getTwitchRequest("https://api.twitch.tv/kraken", self)
            self.ready = True #if successful, set ready flag
        except request.HTTPError:
            logger.warning("Twitch access token verification failed, requesting a new one...")
            #something went wrong, probably our token being invalid
            self.getToken()

    def receiveToken(self, token, state):

        """
        Handles a successfull token grant
        """

        #XSS protection
        if not state == self.state:
            logger.error("State of token response didn't match application defined state.")
            self.token = None
        try:
            res = getJSONRequest(request.urlopen("https://api.twitch.tv/kraken/oauth2/token", "client_id={0}&client_secret={1}&grant_type=authorization_code&redirect_uri=http://localhost/oauth&code={2}&state={3}".format(self.id, self.secret, token, state).encode()))
            self.token = res["access_token"]
            logger.info("Access token successfully retrieved!")
        except:
            self.token = None
            logger.exception("Failed to retrieve access token from Twitch.")
            raise

        #shutdown server
        self.ready = True
        return

    def getToken(self):

        """
        Loads token from cache or requests a new one
        """

        #Is the Twitch feature configured properly?
        if not (self.id and self.secret):
            logger.error("Twitch interface is not configured correctly, check your configuration file!")
            return

        #Setting up server
        self.authServer = OAuthServer(("", 80), self.receiveToken)
        self.serverThread = threading.Thread(target=self.authServer.serve_forever)
        self.serverThread.start()

        #Setting up webinterface
        uri = "http://localhost/oauth"
        scope = "viewing_activity_read"
        self.state = str(uuid.uuid4().int) #get a random UUID to use as state variable

        logger.debug("Redirecting...")
        webbrowser.open("https://api.twitch.tv/kraken/oauth2/authorize?response_type=code&client_id={0}&redirect_uri={1}&scope={2}&state={3}".format(self.id, uri, scope, self.state))
        logger.debug("Waiting for server to terminate...")
        self.serverThread.join()

    def load(self):

        """
        Load config information
        """

        self.id = self.config.getElementText("twitch.clientID", create=True)
        self.secret = self.config.getElementText("twitch.clientSecret", create=True)
        self.checkToken(self.config.getElementText("twitch.token", create=True))

    def save(self):

        """
        Save config information
        """

        self.config.setElementText("twitch.clientID", self.id)
        self.config.setElementText("twitch.clientSecret", self.secret)
        self.config.setElementText("twitch.token", self.token)
        self.config.save()
