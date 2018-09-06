#Discord ProtOS Bot
#
#Author: Jascha "fredi_68" Hirsekorn
#
#Voice recognition and tts support
#This will have to wait until discord.py has properly implemented voice packet reading
#UPDATE: Fuck that. Did my own research. Gonna hook into the voice client UDP socket directly and process audio myself.
#The bright side is that this should still work even after the rewrite. Just have to find the socket again.

#IMPORTS

import asyncio
import audioop
import struct
import platform
import ctypes
import array
import logging
import discord
import socket

import version

#Audio jitter buffer settings
MAX_BUFFER_SIZE = 2048 #maximum amount of OPUS packets stored per voice socket
HIGH_BUFFER_SIZE = 1024 #amount of OPUS packets to keep if the buffer is cleared out due it reaching its maximum capacity
MIN_BUFFER_SIZE = 16 #minimum amount of OPUS packets stored per voice socket. Used to make sure there is still enough space in the buffer to fix message order and properly time the frames.

HAS_VOICE_REQ = True #Since this is an optional part of the code we have to make sure it properly loads even if the necessary libraries are not installed or malfunctioning

DEBUG_GCS = True #True if Google Cloud Speech hasn't been set up yet and module is being tested locally. Set this if you don't have your credentials yet

logger = logging.getLogger("Voicecom")

logger.info("Loading Google Cloud libraries...")
try:
    from google.cloud import speech
except ImportError:
    logger.error("Failed to load Google Cloud libraries: Module could not be imported.")
    HAS_VOICE_REQ = False
except:
    logger.error("Failed to load Google Cloud libraries: An error occured while importing the module.")
    HAS_VOICE_REQ = False

logger.info("Loading PyNaCl...")
try:
    import nacl
except ImportError:
    logger.error("Failed to load PyNaCl: Module could not be imported.")
    HAS_VOICE_REQ = False
except:
    logger.error("Failed to load PyNaCl: And error occured while importing the module.")
    HAS_VOICE_REQ = False

if not discord.opus.is_loaded():
    #OPUS should already be loaded by the main program, if it isn't it is most likely due to an error. Thus we will skip all the fancy config stuff and just fall back to standard paths.
    logger.warn("OPUS was not loaded on program startup! Attempting to load opus library...")
    try:
        defaultLibPath = "32"
        if platform.architecture()[0] == "64bit": #we've got a 64bit system; since discord.py is very picky about the location and the name of the opus library, change the default to make sure users without a config don't run into problems (at least on windows this should work)
            defaultLibPath = "64"
        discord.opus.load_opus("bin/opus/opus"+defaultLibPath)
    except:
        logger.error("OPUS could not be initialized. Please check your config!")
        HAS_VOICE_REQ = False

#Makeshift opus decoder built on the discord.py opus encoder. Now on to figure out which function I have to call...
#Most code is adapted from discord.opus.Encoder cause I am too lazy to do my own research

#VARIABLES
from discord.opus import _lib, OpusError, c_int16_ptr, log, c_int_ptr
c_char_ptr = ctypes.POINTER(ctypes.c_char)
c_ubyte_ptr = ctypes.POINTER(ctypes.c_ubyte)
c_int32_ptr = ctypes.POINTER(ctypes.c_int32)

class DecoderStruct(ctypes.Structure):

    pass

DecoderStructPtr = ctypes.POINTER(DecoderStruct)

#Set argtypes:

_lib.opus_decode.argtypes = [DecoderStructPtr, c_char_ptr, ctypes.c_int32, c_int16_ptr, ctypes.c_int, ctypes.c_int]
_lib.opus_decode.restype = ctypes.c_int

_lib.opus_decoder_create.argtypes = [ctypes.c_int, ctypes.c_int, c_int_ptr]
_lib.opus_decoder_create.restype = DecoderStructPtr

_lib.opus_decoder_destroy.argtypes = [DecoderStructPtr]
_lib.opus_decoder_destroy.restype = None

class _OpusDecoder(discord.opus.Encoder):

    """
    The makeshift Opus decoder.
    Most methods have been adapted from discord.opus.Encoder,
    I've mostly just changed all the ctypes calls to reference the decoder instead of the encoder functions.
    """

    def decode(self, data, is_lost=False):

        """
        Makeshift opus decoder function. Had to rewrite most of the code of the Decoder.decode() method for this.
        """

        #Sooo... I've been thinking
        #Also been reading the Opus docs multiple times and I now believe that I finally know what is going on:
        #There is a certain framesize of audio packet data in milliseconds that the encoder/decoder expects to compile into one packet
        #However, my experiments with arbitrary amounts of audio data have proven that the encoder does indeed encode all lengths of
        #sample data which led me to belive that the codec could handle variable frame lengths. Which is something I still belive in...
        #...at least for the encoder. Since the decoder always just returns an empty sequence of bytes (just a bunch of zeros) I figure that
        #it is actually WAITING on the remaining sample data to be delivered in subsequent packets, which, of course, in our tests never arrived.
        #TL;DR I got packet size and frame length mixed up. Gonna try this with different lengths of data now
        #EDIT: This worked the whole time. Just had to call the decode method a second time. Likes to keep itself a filled buffer apparently.

        #After digging through the OPUS demo source, I finally figured out how FEC works:
        #We may ONLY EVER set the FEC flag if we encounter a frame that has actually been lost. Otherwise the decoder won't work properly.

        pcm = (ctypes.c_int16 * (self.frame_size))() #creating pcm buffer (array of short pointers)
        pcmLength = len(pcm)
        pcm_p = ctypes.cast(pcm, c_int16_ptr)
        
        if data:
            
            #length = ctypes.cast(len(data),ctypes.c_int32) #size of the audio packet, put it into a pointer
            length = len(data)

        else:
            #length = ctypes.cast(0,ctypes.c_int32) #This is in case the encoder has to deal with packet loss, in which case we send a None value
            length = 0

        ret = _lib.opus_decode(self._state, data, length, pcm_p, self.frame_size, 1 if is_lost else 0) #ONLY set FEC flag if we are experiencing actual packet loss
        if ret < 0: #The usual error checking...
            log.info('error has happened in decode')
            raise OpusError(ret)

        #Further adjust this if necessary, but be VERY CAREFUL since exceeding array boundaries can result in application hangs and crashes.
        return array.array('h', pcm[:self.frame_size//2]).tobytes() #changing the array limit was the key, decoder works now. However, the tie-in to Discord does not.

    def __del__(self):

        """
        This is where the encoder/decoder is destroyed.
        """

        if hasattr(self, '_state'):
            _lib.opus_decoder_destroy(self._state)
            self._state = None

    def _create_state(self):
        
        """
        This is where the encoder/decoder is created. We need to switch this to make decoding possible.
        """

        #Works. Can't believe it myself but it works.
        ret = ctypes.c_int()
        result = _lib.opus_decoder_create(self.sampling_rate, self.channels, ctypes.byref(ret))

        if ret.value != 0:
            log.info('error has happened in state creation')
            raise OpusError(ret.value)

        return result

    def set_bitrate(self, kbps):
        
        return 0 #Not implemented for Opus Decoder

    def set_bandwidth(self, req):
        
        return 0 #Not implemented for Opus Decoder

    def set_signal_type(self, req):
        
        return 0 #Not implemented for Opus Decoder

    def set_fec(self, enabled=True):
        
        return 0 #Not implemented for Opus Decoder

    def set_expected_packet_loss_percent(self, percentage):
        
        return 0 #Not implemented for Opus Decoder

class AudioSource():

    def __init__(self, buffer):

        """
        Standard Audio Source interface.
        This class should be subclassed for usage and read from an audio source of your choice instead of a buffer.
        The main purpose of this class is to provide a standardized interface for the VoiceHandle.
        """

        self.buffer = buffer
        self.active = False

    def setActive(self, state):

        """
        Set if this audio source should be read from.
        Usefull for limiting the amount of processed audio data or blocking certain channels from processing audio.
        This method may or may not be effective depending on the selected Google Cloud Speech plan.
        """

        self.active=bool(state)

    def toggleActive(self):

        """
        Alternative method that toggles the active state instead of setting it manually.
        Shorthand for AudioSource.setActive(not AudioSource.active)
        """

        self.active = not self.active

    def read(self, length=0):

        """
        Standardized reading method.
        This method should be overridden by subclasses and should take one keyword argument describing the maximum size of the data buffer returned.
        It should return a bytes object containing the PCM audio data frames.
        """

        return self.buffer.read(length)

    def processText(self, text):

        """
        Standardized return callback. This method will be called each time the Google Cloud Speech API processes a bit of audio.
        This method should be overridden by subclasses and should take one argument containing the text returned by the Google Cloud Speech API.
        The text output will NOT be syncronized or timed, the subclass is responsible for formatting the received text data to make sense in the
        given context. The method should return True for a successful and False for a failed processing call.
        """

        return True

class _voiceHandleDummy():

    def __init__(self):

        pass

class _voiceHandle(_voiceHandleDummy):

    def __init__(self):

        """
        Interface to the Google Cloud Speech API.
        Takes AudioSources and converts their audio data to text for further processing.
        """

        self.ready = False
        if not DEBUG_GCS: #Skip this if we are debugging the voice handle. This will leave the ready attribute at False to make sure the caller doesn't do anything stupid
            try:
                self.client = speech.Client() #Initialize Google Cloud Speech backend
                self.ready = True
            except:
                logger.exception("Google Cloud Speech client could not be initialized.")
        self.audioSources = [] #not quite sure how I want to manage audio input yet... But I definitely want a way to toggle audio processing for certain channels, so that will happen at some point
        
    def registerSource(self, source):

        """
        Register an AudioSource to read audio data from.
        source must be an instance of AudioSource or a subclass thereof.
        """

        if not isinstance(source, AudioSource):

            raise ValueError("source must be of type AudioSource!")

        self.audioSources.append(source)
        return True

    def unregisterSource(self, source):

        """
        Unregister a registered AudioSource.
        """

        if not source in self.audioSources:

            raise ValueError("Source must be registered!")

        self.audioSources.remove(source)
        return True

class VoicePacket():

    def __init__(self, data):

        """
        Parse binary data into fields
        """

        #These are defined by the discord voice packet protocol and will always be the same for every packet unless the API changes. Which it definitely will. Eventually.
        self.type = b"\x80"
        self.version = b"\x78"
        #if we are for some reason unable to decode these they should be left on 0 to make sure there are no issues with processing algorithms later.
        #I'll probably just do some interpolation or something, dunno
        self.sequence = 0
        self.timestamp = 0
        self.ssrc = 0

        try:
            self.type, self.version, self.sequence, self.timestamp, self.ssrc = struct.unpack(">BBHII", data[:12])
        except:
            logger.warning("Unable to decode voice packet meta data.") #Since it turns out that these are actually quite important we'll warn the user if anything happens

        try:
            self.data = data[12:]
        except:
            self.data = b""

    def to_bytes(self):

        """
        Return the packet content as a bytes object (essentially reversing the parsing process).
        """

        try:
            return struct.pack(">BBHII", self.type, self.version, self.sequence, self.timestamp, self.ssrc) + self.data
        except:
            #This should absolutely NEVER happen
            return b""

    def __repr__(self):

        return "<VoicePacket instance (type: "+self.type.decode(encoding="ASCII",errors="backslashreplace")+", version: "+self.version.decode(encoding="ASCII",errors="backslashreplace")+", sequence: "+str(self.sequence)+", timestamp: "+str(self.timestamp)+", ssrc ID: "+str(self.ssrc)+")>"

    def __lt__(self, obj):

        #Make VoicePackets sortable (important for packet order processing)
        if not isinstance(obj, self.__class__):
            return False
        return self.timestamp < obj.timestamp

    def __str__(self):

        return repr(self)

class SocketHandle(asyncio.DatagramProtocol):
#class SocketHandle():

    logger = logging.getLogger("VoiceSocketHandle")

    def __init__(self, listener, voiceclient):

        """
        UDP voice socket protocol.
        Read voice data frames, convert them into packets,
        order them and produce PCM bytestrings readable by other libraries
        """

        #Alright so slight issue here:
        #Since there can be an arbitrary amount of clients in a voice chat at once (at least in theory) we can't predetermine how many decoders we will need
        #since we don't know how many audio sources there will be. Further, the amount of clients can change during a session so our code needs to be
        #prepared to handle it. Meaning that if we encounter an unknown SSRC we have to create a new decoder before attempting audio decoding. Then there is
        #the problem of GC. If we don't have access to WS events there is no way for us to know if a client has left the session (since he may as well be muted).
        #So we should consider propagating changes of voice state to this class if possible

        super().__init__()

        self.logger.debug("New SocketHandle created.")

        self.listener = listener
        self.voiceclient = voiceclient
        self.box = nacl.secret.SecretBox(bytes(self.voiceclient.secret_key)) #Decryption
        self.decoders = {}
        self.buffers = {}
        self.timestamps = {}
        self.pcmBuffer = b""
        self.transport = None

        self.loop = asyncio.get_event_loop()

        #So far using asyncios internal datagram enpoint system has NOT worked out for us...
        #So I will now attempt to do what I saw someone else do and do voice socket polling manually.
        #EDIT: Doesn't work either. The fact that this is a from a merge request on the discord.py
        #repo that is verly likely to be approved makes me think that this is either a windows only
        #problem or something is wrong with my machine.

        #self.loop.create_task(self._poll_socket()) #start packet listener

    async def _poll_socket(self):

        while self.voiceclient.is_connected():
            packet = await self.loop.sock_recv(self.voiceclient.socket, 65536)
            self.datagram_received(packet, (None, 0))

        self.connection_lost(None)

    def connection_made(self, transport):
        
        self.registerTransport(transport)

    def registerTransport(self, transport):

        """
        Register the Transport corresponding to this Protocol to make sure it doesn't get GCed prematurely.
        Only register the Transport that belongs to this Protocol, otherwise there WILL be weird stuff happening.
        This is not ideal I know. Sue me motherfucker.
        """

        self.logger.debug("Connection established. Listening for packets...")

        self.transport = transport

    def connection_lost(self, exc):
        
        #There is a problem here. The bot crashes every time it leaves the voice channel if the interceptor bound a SocketHandle to the voice socket.
        #Apparently, the underlying asyncio loop produces an uncaught error that has something to do with an invalid socket handle.
        #I'd place my bet on a race condition between the socket disconnecting and the handle being invalidated but since it happens EVERY TIME
        #that doesn't sound quite right.

        self.logger.debug("Connection lost, cleaning up...")

        self.listener._disconnectHandle(self)

    def datagram_received(self, data, addr):
        
        #We can't actually decode in this step yet since OPUS is a stateful encoder, or in different words, order and source of the packet matter.
        #Before we can decode anything we have to first align the packets in order, check if any data is missing and sort them by source client.
        #For this we use sequence (order of packets), timestamp (time of arrival and possibly hint towards dropped packets) and ssrc (source ID)

        self.logger.debug("Packet received, processing...")

        packet = VoicePacket(data)
        if packet.data:
            #decrypt data
            nonce = bytearray(24)
            nonce[:12] = data[:12] #encryption nonce
            try:
                packet.data = self.box.decrypt(packet.data, bytes(nonce)) #decrypt packet payload
                #packet.data = self.box.decrypt(packet.data)
            except:
                self.logger.warning("Faulty packet encountered, skipping...")
                return #ignore faulty packets

        self._writeToBuffer(packet) #send the packet to the buffer

    def _writeToBuffer(self, packet):

        """
        Internal method.
        Write OPUS data packets to internal buffer
        """

        #Here we go.
        #At this step we already have to consider decoding. Because OPUS is a stateful codec, it needs to process ALL audio (even if its contents are unknown
        #due to packet loss) which means that if the total stored amount of packets exceeds our set maximum, just deleting the older ones to make room would
        #leave the decoder in an unoptimal state to decode further audio. Thus, if we absolutely NEED to remove audio, we should do it in bursts so the buffer
        #doesn't bottleneck, which would be devastating for our event loop (worst case: Crash the whole application). We should also implement an additional
        #decode method that internally processes packets before their content is distributed. That way, we can use it to clear out the buffer as well

        #We also need to split packets into different buffers for the different sources. This serves to solve two issues:
        #First, only using one buffer would lead to the buffer reaching its maximum (and being cleared our) faster the more audio sources there are.
        #At a certain point this would lead to a bottleneck in the buffer.
        #Second, this makes implementing the decoder way easier since the packets are already presorted after packet source so we only have to look at
        #ToA and sequence

        #Running this setup in an actual voice chat so far hasn't produced the results I was hoping for. Maybe I should reconsider using just in time decoding
        #each time we receive a packet in sequence, but first I want to KNOW why it isn't working. I've confirmed that the decoder is fixed so something in this
        #phase must be going wrong and I don't think trial and error will get us very far from here on out.

        #Check if we already have a buffer for this source and create it if necessary

        self.logger.debug("Got new packet: " + str(packet))

        if packet.ssrc in self.buffers.keys():
            buffer = self.buffers[packet.ssrc]
        else:
            self.logger.debug("Encountered unknown SSRC, creating new audio buffer...")
            buffer = [] #create new buffer
            self.buffers[packet.ssrc] = buffer

        buffer.append(packet) #Add packet
        if len(buffer) > MAX_BUFFER_SIZE:
            self.logger.debug("Buffer size above maximum limit, clearing buffer...")
            self._readPackets(MAX_BUFFER_SIZE-HIGH_BUFFER_SIZE-1, [packet.ssrc]) #the -1 is a fail safe

    def _readPackets(self, n, buffers=None):

        """
        Internal method
        This method should be called every time the buffer for one or multiple clients has to be cleared our or audio data was requested.
        n specifies how many packets should be converted, buffers specify which buffers to read from. If None, all buffers will be examined.
        """

        if not buffers:
            
            buffers = self.buffers.keys() #read from all buffers (this also means that we will read until the first buffer reaches the minimum)
            self.logger.debug("No buffers specified, reading from all available audio sources: ")
            self.logger.debug("Buffers: " + str(tuple(buffers)))

        ret = b""
        for i in range(0,n): #Process at max n packets
            frame = [] #unmixed frame data (PCM)
            for k in buffers:
                buf = self.buffers[k]

                if len(buf) <= MIN_BUFFER_SIZE: #This buffer is empty, 
                    self.logger.debug("Buffer " + str(k) + " is exhausted, stopping audio decoding")
                    continue

                buf.sort() #this SHOULD sort all packets by timestamp

                #Get OPUS decoder
                if k in self.decoders.keys():
                    decoder = self.decoders[k]
                else:
                    self.logger.debug("No decoder present for " + str(k) + ", creating new instance.")
                    decoder = _OpusDecoder(48000, 2) #If it doesn't exist, the decoder is created on the fly
                    self.decoders[k] = decoder

                packet = buf.pop(0) #Get first packet
                if k in self.timestamps.keys():
                    timestamp = self.timestamps[k]
                else:
                    timestamp = packet.timestamp - decoder.frame_size #Estimate frame duration to be decoder.frame_size
                
                if packet.timestamp <= timestamp:
                    #We either have a wrap around or an error. Since I'm too lazy to code a proper solution we'll again just assume that the audio data has the duration of
                    #decoder.frame_size
                    timestamp = packet.timestamp - decoder.frame_size

                #Now decode the packet
                try:
                    #frame.append(decoder.decode(packet.data,packet.timestamp-timestamp))
                    self.logger.debug("Decoding packet...")
                    decodedData = decoder.decode(packet.data)
                    self.logger.debug("Got " + str(len(decodedData)) + " byte(s) of data.")
                    frame.append(decodedData)
                except:
                    self.logger.exception("OPUS packet could not be decoded: ")

                self.timestamps[k] = packet.timestamp #update the timestamp

            if len(frame) <= 0: #we have exhausted all buffers, stop handling packets
                self.logger.debug("Ran out of audio data, stopping audio decoding.")
                raise RuntimeError("No audio available")

            #Right... now we have to actually mix the different audio signals together

            if len(frame) <= 1:
                ret += frame[0]
                continue

            #TODO: Check if this actually works as intended

            pcm = frame[0]
            for i in range(1, len(frame)):
                mixedmax = audioop.max(pcm, 2)
                newmax = audioop.max(i, 2)
                factor = 1
                if mixedmax + newmax >= 255:
                    factor = ((mixedmax + newmax)/255) #calculate the factor by which to dampen the audio signals befor merging so that no clipping happens
                    factor += (1-factor)/2 #distribute the factor so both signals are evenly dampened
                try:
                    pcm = audioop.add(pcm,i,2) #add fragments together
                except audioop.error as e:
                    logging.warning("Audio frame could not be mixed: " + str(e))
            #Add the frame data to the return buffer
            ret += pcm

        return ret

    def read(self, length):

        """
        Process packets from buffer and read the resulting PCM datastream.
        length parameter specifies how many bytes will be read.
        """

        #TODO: Add special cases for when length is negative (= read until buffer is empty)

        if length < 0:
            raise ValueError("length must be positive!")

        while len(self.pcmBuffer) < length:
            try:
                newdata = self._readPackets(1)
            except RuntimeError:
                #buffer probably empty
                break
            self.pcmBuffer += newdata #add more data to the bytestream

        if len(self.pcmBuffer) <= length:
            #If we don't have as much data as requested or just enough, we return what we have and reset the buffer
            ret = bytes(self.pcmBuffer)
            self.pcmBuffer = b""
        else:
            ret = bytes(self.pcmBuffer[:length]) #Otherwise we truncate the internal buffer and return the requested bytes
            self.pcmBuffer = self.pcmBuffer[length:]

        return ret

    def closeHandle(self):

        """
        Closes the respective Transport and makes sure both it and the Protocol are GCed.
        Call this after the voice socket has closed, the processing algorithm has terminated or an internal error occured.
        """

        #Since the Protocol is actually bound to the Transport and not the other way around (although, that would be much easier for us) we have to close the Transport for the
        #Protocol to be GCed. Just closing it should be fine. Also don't forget to delete any references to it.
        if self.transport and not self.transport.is_closing():
            #fist, we try to close the connection the "nice" way
            if hasattr(self.transport, "can_write_eof") and self.transport.can_write_eof():
                try:
                    self.transport.write_eof()
                except:
                    pass #something went wrong... perhaps the method was STILL not implemented?
            #request a connection termination, everything else is left to the transport
            self.transport.close()
            #Does cross-referencing present an issue for GC? We will make sure to delete any cross references anyway, just so nothing weird happens
            #(Finding and closing memory leaks later would be a pain in the arse)
            self.transport = None

    def poll(self):

        """
        Returns if data is ready to be read
        """

        return bool(max(0, len(self.pcmBuffer))) or bool(max([0].extend(map(self.buffers, len))))

    def flush(self):

        """
        Resets the internal PCM buffer to remove any leftover decoded audio.
        This can be useful if the stream hasn't been read in a while and the buffer content is really old.
        Call this every time you start capturing audio from a transport.
        """

        self.pcmBuffer = b""

class _ConnectionListenerDummy():

    def __init__(self, client):

        pass

    def updateChannels(self):

        pass

    def _disconnectHandle(self, handle):

        pass

    def _connectHandle(self, voiceclient):

        pass

    def getAudio(self, channel, length=0):

        return b""

class _ConnectionListener(_ConnectionListenerDummy):

    logger = logging.getLogger("Listener")

    def __init__(self, client):

        """
        Create a new ConnectionListener object.
        The Connection listener will replace the join_voice_channel method of client with its own hook method.
        It will automatically wait for a voice channel to connect and then provide audio through the
        getAudio() method.
        """

        self.client = client

        async def join_voice_channel(channel):

            """
            Connection Listener voice client registration method.
            This method intercepts any calls to discord.client.Client.join_voice_channel() to insert its detection code.
            The method will otherwise work as per usual.
            Returns a fully initialized VoiceClient object.
            """

            ret = await discord.client.Client.join_voice_channel(self.client, channel) #Do what the method was originally meant to do
            self.logger.debug("Intercepted voice client initialization. Updating handlers...")
            await self.updateChannels() #calls the update method on the Packet Listener
            return ret

        self.client.join_voice_channel = join_voice_channel #replace the method with our interceptor function

        self.logger.debug("Interceptor method bound to client instance.")

        self.handles = []

    async def updateChannels(self):

        """
        Check for new voice channels and register their sockets on the listener.
        Also removes disconnected voice channels from the listener.
        """

        for i in self.client.voice_clients:
            has_listener = False
            for j in self.handles:
                if j.voiceclient == i:
                    has_listener = True
            if has_listener:
                continue #we already have a listener registered to this voice client, skip it
            #Add a new handle for this voice client and intercept default packet handling
            self.logger.debug("Found new voice connection, intercepting UDP socket transmission...")
            await self._connectHandle(i)

        for i in self.handles:
            if not i.voiceclient in self.client.voice_clients:
                #voice connection died, either the handle is already shutting down or didn't notice, either way we will close it and leave the rest to GC
                self.logger.debug("Found dead voice connection, closing transports...")
                await self._disconnectHandle(i)

    async def _connectHandle(self, voiceclient):

        #Right, so I finally figured this shit out
        #The voice websocket is never actually CONNECTED, it just serves as a generic socket to send data from.
        #This is bad for us since it means that datagrams will never reach us, so we need to get the connection information,
        #then set up a voice socket ourselves.
        #Luckily, after the voice websocket sends the select protocol packet, we know our voice socket port and our external IP.
        #We can access these through the websocket stored in voiceclient.ws._connection
        #However, these values may or may not be present at initialization time so we need to wait until they are

        self.logger.debug("Waiting for IP discovery...")
        while True:
            if hasattr(voiceclient, "ws") and hasattr(voiceclient.ws, "_connection") and hasattr(voiceclient.ws._connection, "port") and hasattr(voiceclient.ws._connection, "ip"):
                break
            await asyncio.sleep(0.2)

        ip = voiceclient.ws._connection.ip
        port = voiceclient.ws._connection.port

        self.logger.debug("UDP Voice Socket connection information is " + str(ip) + ":" + str(port))
        self.logger.debug("UDP Voice Socket remote endpoint is " + str(voiceclient.endpoint_ip) + ":" + str(voiceclient.voice_port))

        self.logger.debug("Connecting...")
        try:
            #No idea why this doesn't work... it really SHOULD
            transport, handle = await self.client.loop.create_datagram_endpoint(lambda: SocketHandle(self, voiceclient), sock=voiceclient.socket)
            #transport, handle = await self.client.loop.create_datagram_endpoint(lambda: SocketHandle(self, voiceclient), local_addr=("0.0.0.0", port), remote_addr=(voiceclient.endpoint_ip, voiceclient.voice_port)) #connect to UDP voice socket
            
            #handle = SocketHandle(self, voiceclient)
            
        except socket.error:
            self.logger.exception("An error occured while trying to connect to voice socket: ")
            return

        self.handles.append(handle) #keep a reference to the handle

    async def _disconnectHandle(self, handle):

        if handle in self.handles:
            self.handles.remove(handle)
            handle.closeHandle()

    async def getAudio(self, channel, length=0):

        """
        Read audio data from a channel.
        channel must have a SocketHandle registered for this call to be successful.
        Optional parameter length specifies how much data to read.
        Returns a bytes object containing the PCM encoded audio data.
        """

        for handle in self.handles:
            if handle.voiceclient.channel == channel: #found the corresponding handle
                return handle.read(length)
        raise ValueError("No registered packet handle for channel " + str(channel) + " !")

if HAS_VOICE_REQ: #ensure functionality without voice libraries
    VoiceHandle = _voiceHandle
    ConnectionListener = _ConnectionListener
else:
    VoiceHandle = _voiceHandleDummy
    ConnectionListener = _ConnectionListenerDummy
