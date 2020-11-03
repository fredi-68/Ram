import logging
import asyncio
import bisect

import nacl
from discord.opus import OpusError

from .opus import OpusDecoder
from .rdp import VoicePacket
from .constants import *

BUFFER_CLEAR_SIZE = MAX_BUFFER_SIZE - HIGH_BUFFER_SIZE

class ChannelHandle(asyncio.DatagramProtocol):

    logger = logging.getLogger("Voicecom.ChannelHandle")

    def __init__(self, listener, client):

        super().__init__()

        self.logger.debug("New ChannelHandle created.")

        self.listener = listener
        self.voiceclient = client
        self.box = nacl.secret.SecretBox(bytes(self.voiceclient.secret_key)) #Decryption
        self.decoders = {}
        self.buffers = {}
        self.user_map = {}
        self.ssrc_map = {}
        self.transport = None

        self.decryption_method = getattr(self, "_decrypt_rtp_" + client.mode)

        self.loop = asyncio.get_event_loop()

    def map_user(self, ssrc, user):

        assert user is not None
        self.user_map[ssrc] = user

    def _get_ssrc_for_user(self, user):

        for ssrc, usr in self.user_map.items():
            if usr == user:
                return ssrc
        raise KeyError("No such user")

    def _get_user_for_ssrc(self, ssrc):
        
        return self.user_map[ssrc]

    def allocate_connection(self, ssrc):
        
        self.logger.debug("New client connecting, allocating resources for SSRC %i..." % ssrc)
        self.decoders[ssrc] = OpusDecoder()
        self.buffers[ssrc] = b""

    def free_connection(self, ssrc):

        self.logger.debug("Client disconnecting, freeing resources for SSRC %i..." % ssrc)
        del self.decoders[ssrc]
        del self.buffers[ssrc]

    def connection_made(self, transport):
        
        self.registerTransport(transport)

    def registerTransport(self, transport):

        """
        Register the Transport corresponding to this Protocol to make sure it doesn't get GCed prematurely.
        Only register the Transport that belongs to this Protocol, otherwise there WILL be weird stuff happening.
        This is not ideal I know. Sue me motherfucker.
        """

        self.logger.debug("Connection established. Listening for packets...")
        self.logger.debug("Transport type is %s" % str(type(transport)))

        self.transport = transport
        self.loop.create_task(self._fix_discords_shit())

    async def _fix_discords_shit(self):

        self.logger.debug("Fixing discords shit...")
        await self.voiceclient.ws.speak()
        await asyncio.sleep(0.5)
        self.voiceclient.send_audio_packet(b'\xF8\xFF\xFE', encode=False)
        await self.voiceclient.ws.speak(False)

    def _decrypt_rtp_xsalsa20_poly1305_lite(self, packet):
        nonce = bytearray(24)
        nonce[:4] = packet.data[-4:]
        voice_data = packet.data[:-4]
        result = self.box.decrypt(bytes(voice_data), bytes(nonce))

        return result

    def _decrypt_rtp_xsalsa20_poly1305_suffix(self, packet):
        nonce = packet.data[-24:]
        voice_data = packet.data[:-24]
        result = self.box.decrypt(bytes(voice_data), bytes(nonce))

        return result

    def _decrypt_rtp_xsalsa20_poly1305(self, packet):
        nonce = bytearray(24)
        nonce[:12] = packet.header
        result = self.box.decrypt(bytes(packet.data), bytes(nonce))

        return result

    def _readPackets(self, count, source):

        """
        Read count packets from the specified source.
        Returns PCM audio data.
        """

        if source in self.decoders:
            decoder = self.decoders[source]
        else:
            self.logger.debug("Unknown SSRC encountered, creating new decoder state...")
            decoder = OpusDecoder()
            self.decoders[source] = decoder
        buffer = self.buffers[source][:count]
        self.buffers[source] = self.buffers[source][count:] #truncate the buffer

        #decode audio
        pcm = b""
        for packet in buffer:
            try:
                data = decoder.decode(packet.data)
            except OpusError as e:
                self.logger.error("Error happened in opus decoder: %s" % str(e))
                return ""
            pcm += data

        return pcm

    def _writeToBuffer(self, packet):

        self.logger.debug("Got new packet: " + str(packet))

        if packet.ssrc in self.buffers.keys():
            buffer = self.buffers[packet.ssrc]
        else:
            self.logger.debug("Encountered unknown SSRC, creating new audio buffer...")
            buffer = [] #create new buffer
            self.buffers[packet.ssrc] = buffer


        #buffer.append(packet) #Add packet
        bisect.insort(buffer, packet) #This should be more efficient than inserting and sorting later
        if len(buffer) > MAX_BUFFER_SIZE:
            self.logger.debug("Rendering last %i packets for SSRC %i..." % (BUFFER_CLEAR_SIZE, packet.ssrc))
            data = self._readPackets(BUFFER_CLEAR_SIZE, packet.ssrc)
            self.listener.write(data, packet.ssrc, self)

    def datagram_received(self, data, addr):

        self.logger.debug("Packet received, processing...")

        if 200 <= data[1] <= 204:
            self.logger.debug("RTCP packet encountered, skipping...")
            return

        packet = VoicePacket(data)
        if packet.data:
            #decrypt data
            self.logger.debug("Decrypting...")
            try:
                data = self.decryption_method(packet)
                if packet.extended:
                    offset = packet.update_ext_headers(data)
                    packet.data = data[offset:]
                else:
                    packet.data = data
            except:
                self.logger.warning("Faulty packet encountered, skipping...")
                return #ignore faulty packets

        self._writeToBuffer(packet) #send the packet to the buffer
