import asyncio
import logging
import socket
import audioop

import discord
from discord.opus import OpusError

from .channel import ChannelHandle
from .rdp import *
from .constants import *
from .opus import OpusDecoder
from .enums import SinkType
from .speech import SphinxRE
from .sinks import SpeechRecognitionBuffer, ReplayBuffer

logger = logging.getLogger("Voicecom")

class ConnectionListener():

    """
    This class is doing all the work related to injecting our
    code into the library and exposing the API.

    Code injection is done through substituting method references for
    custom wrappers that execute arbitrary code.
    For example, calling VoiceChannel.connect() calls the normal function,
    then runs a custom subroutine that registers the channel on the listener
    and returns.
    This technique allows this library to remain separate from discord.py and
    does not require any actual manipulation of the libraries own code.
    """

    logger = logging.getLogger("Voicecom.ConnectionListener")

    def __init__(self, client, recognizer=None):

        self.handles = {}
        self.sr_sinks = {}
        self.rpb_sinks = {}
        self.client = client
        self.sinks = []
        self.voice_command_callback = None
        if not recognizer:
            try:
                self.recognizer = SphinxRE()
            except RuntimeError:
                self.logger.warn("Unable to initialize SphinxRE, speech recognition will not be available.")
                self.recognizer = None
        else:
            self.recognizer = recognizer
        self._patch()

    def _patch(self):

        """
        Patches the discord.py library to allow for interception of connection/disconnection
        and voice ws events.
        This code is very dodgy and likely to break between discord.py releases.
        """

        self.logger.debug("Injecting Connectable.connect hook...")
        original = discord.abc.Connectable.connect

        async def connect(obj, *, timeout=60):
            vc = await original(obj, timeout=timeout)
            await self.registerChannelHandle(vc)

            self.logger.debug("Injecting DiscordVoiceWebSocket.receive_message hook...")
            async def received_message(msg):

                await self.handle_ws_event(msg, vc)
                return await discord.gateway.DiscordVoiceWebSocket.received_message(vc.ws, msg)

            vc.ws.received_message = received_message

            self.logger.debug("...Success!")
            return vc
            
        discord.abc.Connectable.connect = connect
        self.logger.debug("...Success!")

    async def handle_ws_event(self, msg, client):

        """
        Whenever we add a ChannelHandle for a voice_client, this method is injected into the
        voice WS message handler in order to extract OP 5 SPEAKING events, which are used
        to map user IDs to SSRCs.
        Similarily, OP 12 CLIENT CONNECT and OP 13 CLIENT DISCONNECT are used to preemtively
        allocate and free resources for user connections.
        """

        self.logger.debug("Received voice WS event for client %s: %s" % (str(client.channel), str(msg)))
        op = msg['op']
        data = msg.get('d')

        handle = self.handles[client.channel.id]

        if op == discord.gateway.DiscordVoiceWebSocket.SPEAKING:
            self.logger.debug("Speaking event received, processing speaker SSRC...")
            try:
                ssrc = int(data["ssrc"])
                user_id = int(data["user_id"])
                user = client.channel.guild.get_member(user_id)
                handle.map_user(ssrc, user)
                has_stopped = not data["speaking"]
                if has_stopped:
                    await self.handle_stop_speaking(client, user)
            except:
                self.logger.exception("Unable to set user/SSRC mapping:")

        elif op == discord.gateway.DiscordVoiceWebSocket.CLIENT_CONNECT:
            try:
                ssrc = int(data["audio_ssrc"])
                user_id = int(data["user_id"])
                user = client.channel.guild.get_member(user_id)
                handle.map_user(ssrc, user)
                handle.allocate_connection(ssrc)
            except:
                self.logger.exception("Unable to allocate new SSRC:")

        elif op == discord.gateway.DiscordVoiceWebSocket.CLIENT_DISCONNECT:
            try:
                user_id = int(data["user_id"])
                user = client.channel.guild.get_member(user_id)
                ssrc = handle._get_ssrc_for_user(user)
                handle.free_connection(ssrc)
            except:
                self.logger.exception("Unable to free SSRC:")

    async def handle_stop_speaking(self, client, user):

        if not self.recognizer:
            return

        if not self.voice_command_callback:
            return

        id = client.channel.id
        if not id in self.sr_sinks:
            return

        sink = self.sr_sinks[id]
        data = sink.get_audio(user)

        if data == b"":
            self.logger.debug("Audio buffer was empty, discarding...")
            return

        #Normalize audio
        m = audioop.max(data, 2)
        d = max(32767-m, 0)
        if d:
            data = audioop.mul(data, 2, d/32767)

        self.logger.debug("Analyzing phrase...")
        res = await self.recognizer.recognize(data)
        #self.logger.debug("Speech recognition result: '%s'" % res)
        self.logger.info("Speech recognition result: '%s'" % res)

        try:
            await self.voice_command_callback(res, user, client.channel)
        except:
            self.logger.exception("Error has happened in voice command callback:")

    def registerVoiceCommandCallback(self, cb):

        """
        Registers a callback to run each time a voice command
        is executed.
        The callback should be a coroutine, taking three arguments:
        the transcribed spoken text, the user instance, and the channel instance.
        """

        self.voice_command_callback = cb

    async def registerChannelHandle(self, client):

        self.logger.info("Intercepted voice client creation, creating channel handle...")
        ip = client.ws._connection.ip
        port = client.ws._connection.port
        self.logger.debug("UDP Voice Socket connection information is " + str(ip) + ":" + str(port))
        self.logger.debug("UDP Voice Socket remote endpoint is " + str(client.endpoint_ip) + ":" + str(client.voice_port))
        self.logger.debug("Connecting...")

        try:
            transport, handle = await self.client.loop.create_datagram_endpoint(lambda: ChannelHandle(self, client), sock=client.socket)
            self.handles[client.channel.id] = handle

        except socket.error:
            self.logger.exception("An error occured while trying to connect to voice socket: ")
            return
        self.logger.debug("...Connected!")

        self.logger.debug("Injecting VoiceClient.disconnect() hook...")
        async def disconnect(*, force=False):
            try:
                await self.unregisterChannelHandle(client)
            except:
                pass
            return await discord.VoiceClient.disconnect(client, force=force)
        client.disconnect = disconnect
        self.logger.debug("...Success!")

        self.logger.debug("Creating audio replay buffer...")
        buf = ReplayBuffer()
        self.rpb_sinks[client.channel.id] = buf
        self.addSink(buf, client.channel, type=SinkType.ALL)

        if self.recognizer:
            self.logger.debug("Creating speech recognition buffer...")
            buf = SpeechRecognitionBuffer()
            self.sr_sinks[client.channel.id] = buf
            self.addSink(buf, client.channel, type=SinkType.ALL)

    async def unregisterChannelHandle(self, client):

        id = client.channel.id
        if id in self.handles:
            handle = self.handles[id]
            del self.handles[id]

        if id in self.sr_sinks:
            self.removeSink(self.sr_sinks[id])
            del self.sr_sinks[id]

        if id in self.rpb_sinks:
            self.removeSink(self.rpb_sinks[id])
            del self.rpb_sinks[id]

    def write(self, data, ssrc, channel):

        ch = channel.voiceclient.channel
        #self.logger.debug("ConnectionListener.write() was called with data=%s, ssrc=%s, channel=%s" % (repr(data), str(ssrc), str(channel)))
        user = channel._get_user_for_ssrc(ssrc)
        for sink, t_user, type, t_ch in self.sinks:
            if not ch == t_ch:
                continue

            if type == SinkType.SINGLE and t_user == user:
                sink.write(data, user)
            elif type == SinkType.ALL:
                sink.write(data, user)
            elif type == SinkType.MIX:
                #TODO: Implement
                pass

    def addSink(self, sink, channel, user=None, type=SinkType.MIX):

        self.sinks.append((sink, user, type, channel))

    def removeSink(self, sink):

        for stuff in self.sinks[:]:
            if stuff[0] == sink:
                self.sinks.remove(stuff)
                return
        raise ValueError("No such sink")

    def getReplay(self, channel):

        return self.rpb_sinks[channel.id].save()