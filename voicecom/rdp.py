import logging
import struct

logger = logging.getLogger("RDP")

class VoicePacket():

    def __init__(self, data):

        """
        Parse binary data into fields
        """

        #These are defined by the discord voice packet protocol and will always be the same for every packet unless the API changes. Which it definitely will. Eventually.
        self.type = 0x80
        self.version = 0x78
        self.cc = data[0] & 0b00001111 #Nani?
        self.extended = bool(data[0] & 0b00010000)
        #if we are for some reason unable to decode these they should be left on 0 to make sure there are no issues with processing algorithms later.
        #I'll probably just do some interpolation or something, dunno
        self.sequence = 0
        self.timestamp = 0
        self.ssrc = 0

        try:
            self.type, self.version, self.sequence, self.timestamp, self.ssrc = struct.unpack(">BBHII", data[:12])
        except:
            logger.warning("Unable to decode voice packet meta data.") #Since it turns out that these are actually quite important we'll warn the user if anything happens

        self.header = data[:12]

        self.data = data[12:]

        self.csrcs = ()
        if self.cc:
            fmt = '>%sI' % self.cc
            offset = struct.calcsize(fmt) + 12
            self.csrcs = struct.unpack(fmt, data[12:offset])
            self.data = data[offset:]

    def update_ext_headers(self, data):

        """
        Adds extended header data to this packet, returns payload offset
        THIS CODE WAS TAKEN FROM HERE:
        https://github.com/imayhaveborkedit/discord.py/blob/voice-recv-mk2/discord/rtp.py
        """

        #I couldn't care less about the stuff written in here, all I want to know is where the actual audio data starts
        profile, length = struct.unpack_from('>HH', data)
        values = struct.unpack('>%sI' % length, data[4:4+length*4])

        return 4 + length * 4

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

        return "<VoicePacket instance (type: "+str(self.type)+", version: "+str(self.version)+", sequence: "+str(self.sequence)+", timestamp: "+str(self.timestamp)+", ssrc ID: "+str(self.ssrc)+")>"

    def __lt__(self, obj):

        #Make VoicePackets sortable (important for packet order processing)
        if not isinstance(obj, self.__class__):
            return False
        return self.timestamp < obj.timestamp

    def __str__(self):

        return repr(self)