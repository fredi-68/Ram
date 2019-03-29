import struct
import asyncio
import uuid
import logging

"""
Netcode for ProtOS Discord Bot remote control
"""

class NetworkError(Exception):

    """
    Standard error raised by RC network operations
    """

class IllegalRequestError(NetworkError):

    """
    Error raised when a client has made an invalid request.
    """

    pass

class IllegalReadError(NetworkError):

    """
    Error raised when a client attempts to read from the same channel
    multiple times at once.
    """

    pass

class VersionError(NetworkError):

    """
    Error raised when the client's version doesn't match the remote host
    """

    pass

class NetworkPacket():

    #PACKET STRUCTURE:
    #Packet version: 4 bytes
    #Packet opcode: 2 bytes
    #Packet length: 4 bytes
    #VERSION 1+: Channel ID: 16 bytes
    #Payload: Packet length bytes

    OP_NOOP = 0
    OP_OK = 1
    OP_ERROR = 2
    OP_CONT = 3

    OP_LOGIN = 4
    OP_LOGOUT = 5

    OP_CMD = 6
    OP_UPDATE_INIT = 7
    OP_UPDATE_FILELIST = 8
    OP_UPDATE_TRANSFER = 9
    OP_RATCMD = 10
    OP_CONFIG = 11

    def __init__(self, data=None, channelID=None):

        """
        A packet of network data
        This class manages binary data constructs made up of a header
        and a payload containing one or multiple fields of data.
        
        If channelID is specified, the packet version will be set to version 1 and switch
        to the Channels protocol.
        """

        self.channelID = channelID

        self.version = 0 if not channelID else 1 #set version
        self.opcode = self.OP_NOOP
        self.fields = {}

        if data:
            self._from_bytes(data)

    def addField(self, name, data):

        """
        Add a field to the packet
        """

        self.fields[name] = data

    def getField(self, name):

        """
        Get the field with tag name. Raises KeyError if the key doesn't exist
        """

        return self.fields[name]

    def getFields(self):

        """
        Returns a view of the packets field keys
        """

        return self.fields.keys()

    def setOpCode(self, code):

        """
        Sets the opcode of the packet
        """

        self.opcode = code

    def setChannelID(self, channelID):

        self.channelID = channelID
        if channelID:
            self.version = 1

    def to_bytes(self):

        """
        Converts the packet to a bytestring
        """

        payload = b""
        for field in self.fields.items():
            tag = field[0].encode()
            data = field[1]
            payload += struct.pack(">I",len(tag)) #length of field name
            payload += tag
            payload += struct.pack(">L",len(data))
            payload += data

        header = struct.pack(">IHL",self.version,self.opcode,len(payload))

        #Since protocol version 1 (and the introduction of channels),
        #each packet carries a channel identifier, appended to the 10 byte header.
        #The identifier is a 16 bytes long uuid, as returned by uuid.uuid4().bytes

        if self.version > 0:
            header += self.channelID #add uuid

        return header+payload

    def _from_bytes(self, data):

        """
        Constructs a packet from binary data
        """

        header = data[:10]
        
        self.version, self.opcode, length = struct.unpack(">IHL",header)
        if self.version > 0:
            #Version 1+, we should expect a 16 byte uuid to follow
            self.channelID = data[10:26]
            payload = data[26:] #remove the uuid and header from the payload

        else:
            payload = data[10:] #remove header from payload

        if length > 0:
            i = 0
            while len(payload) - i > 4:
                tagLength = struct.unpack_from(">I",payload,i)[0]
                i += 4
                tag = struct.unpack_from(">"+str(tagLength)+"s",payload,i)[0].decode()
                i += tagLength
                dLength = struct.unpack_from(">L",payload,i)[0]
                i += 4
                d = struct.unpack_from(">"+str(dLength)+"s",payload,i)[0]
                i += dLength
                self.addField(tag,d)

    @classmethod
    async def fromStream(cls, stream):

        """
        Create a packet from a stream
        """

        #Read 10 byte header
        while True: #try until we either get enough bytes or an illegal read happens
            try:
                header = await stream.readexactly(10)
            except asyncio.IncompleteReadError as e:
                #slight issue here: I think we may have a problem where this can loop infinitely if no message is sent, since the reader would receive an empty
                #bytes object every time. This should throw an IncompleteReadError but the partial should ALSO be 0.
                #TL;DR we need a way of detecting that the stream has been closed if e.partial == 0
                if len(e.partial) == 0:
                    pass #let's see what happens if we don't stop partial == 0 from aborting
                raise
            break
        version, opcode, length = struct.unpack(">IHL",header)

        #read the rest of the packet, parsing will be left to the packet

        if version > 0:
            #expect channel uuid
            channelID = await stream.readexactly(16)
            header += channelID #append uuid to header

        if length >0:
            payload = await stream.readexactly(length)
        else:
            payload = b""

        ret = NetworkPacket.__new__(cls,header+payload)
        ret.__init__(header+payload)
        return ret

    def __repr__(self):

        s = "<NetworkPacket("
        s += "protocolVersion="+str(self.version)
        s += ", channelID="+repr(self.channelID)
        s += ", opcode="+str(self.opcode)
        s += ", fields={"
        fields = []
        for i in self.getFields():
            fields.append(id+": "+repr(self.getField(i)))
        s += ", ".join(fields) + "}"
        s += ")>"

        return s

class Channel():

    """
    A Channel for exchanging data.
    This class represents an abstract layer on top of the network connection that makes simultaneous asynchronous
    RPC trivial.

    Channels are identified using a 16 byte UUID.
    A special case is the channel with identifier None. This channel is created when using protocol version 0, which
    doesn't support multi channel connections.
    """

    def __init__(self, connection, channelID):

        """
        Create a new Channel instance.
        Users should generally not use this constructor directly, but
        generate new channels using Connection.createNewChannel().
        """

        self.connection = connection
        self.channelID = channelID

        self._inputBuffer = []

        self.readFuture = None

        self.logger = logging.getLogger("Channel: "+repr(channelID))

    async def sendPacket(self, packet):

        """
        Send a packet using this channel.
        """

        await self.connection._sendPacket(packet)

    async def readPacket(self, packet):

        """
        Read a packet from this channel.
        Attempting to call this method while another task is already waiting for a result will result in an IllegalReadError.
        """

        if self.readFuture != None:
            raise IllegalReadError("Another task is already waiting for a packet on this channel")

        if len(self._inputBuffer) < 1:

            self.logger.debug("No packet queued, suspending task until packet dispatch")
            self.readFuture = asyncio.Future()
            await self.readFuture() #wait for a packet to become available
            self.readFuture = None #reset future so next read can be queued

        return self._inputBuffer.pop(0) #return packet

    def getPacket(self):

        """Return a new packet with default values for communication on this channel"""

        return NetworkPacket(channelID=self.channelID)

    def _handlePacket(self, packet):

        """
        Internal method.
        Receives packets from the connection and notifies code waiting on a packet already.
        """

        self.logger.debug("New packet received")
        self._inputBuffer.append(packet)
        if self.readFuture != None:
            self.logger.debug("Waking suspended tasks...")
            self.readFuture.set_result(True) #notify suspended tasks

class Connection():

    """
    A connection to a remote host.
    """

    logger = logging.getLogger("Connection")

    def __init__(self, reader, writer, loop=None, newChannelCallback=None, requireVersion=0):

        """Wrap a connection using two bytestreams reader and writer.
        If loop is not specified, asyncio.get_event_loop() will be used
        to retrieve an event loop.
        If newChannelCallback is specified, it should be a coroutine
        that takes the new channel as a singular argument.
        If requireVersion is greater 0, it specifies the MINIMUM version of the protocol
        to use. Read or write operations on packets with a version lower than specified will
        raise VersionError.
        
        The new connection wrapper will immediately start listening for packets.
        
        To stop listening, call the close() method."""

        self.version = 1
        self.requireVersion = requireVersion

        self.loop = loop if loop else asyncio.get_event_loop()
        self.reader = reader
        self.writer = writer

        self.newChannelCallback = newChannelCallback

        self.channels = []

        self.isClosed = False

        self.loop.create_task(self._receivePackets()) #start listening for packets

    async def onNewChannel(self, channel):

        """
        Called each time a new channel is created by the remote host.
        Subclasses can override this to implement event handling,
        alternatively, one can specify a newChannelCallback on
        initialization.
        """

        #Our default handler just calls the callback if it exists
        if self.newChannelCallback:
            self.logger.debug("Running new channel callback coroutine...")
            await self.newChannelCallback(channel)

    async def createNewChannel(self):

        """
        Create a new channel. This method will take care of creating a new virtual channel.
        It can then be used like a new connection.
        """

        self.logger.debug("Creating new channel")
        ch = Channel(self, uuid.uuid4().bytes) #create a new channel using a random channel ID
        self.channels.append(ch)
        return ch

    async def _sendPacket(self, packet):

        """
        Send a packet using the internal socket connection.
        """

        if self.isClosed:
            raise IllegalRequestError("Cannot write to closed connection")

        if packet.version < self.requireVersion:
            raise VersionError("Write operation failed: Incompatible packet version.")

        self.logger.debug("Sending packet: "+repr(packet))

        await self.writer.write(packet.to_bytes())

    async def _receivePackets(self):

        """Internal method.
        Wait for packets to arrive and deliver them to channels."""

        self.logger.debug("Listening for packets...")

        while True:

            try:
                packet = await NetworkPacket.fromStream(self.reader)
            except asyncio.IncompleteReadError:
                #If this happens our connection most likely was closed by the remote host
                self.logger.debug("Packet read error encountered, shutting down")
                break

            if packet.version < self.requireVersion:
                raise VersionError("Read operation failed: Incompatible packet version.")

            self.logger.debug("New packet received: "+repr(packet))

            handled = False

            for ch in self.channels:
                if ch.channelID == packet.channelID:
                    self.logger.debug("Dispatching new packet event to channel handler")
                    ch._handlePacket(packet)
                    handled = True
                    break

            if not handled:
                #create a new channel
                self.logger.debug("New channel opened by remote host, dispatching new channel event")
                ch = Channel(self, packet.channelID)
                self.channels.append(ch)
                ch._handlePacket(packet)
                self.loop.create_task(self.onNewChannel(ch)) #run even handler for new channel

        self.close()

    def close(self):

        """
        Closes all channels, ends the session and frees all resources.
        """

        self.logger.debug("Shutting down")

        self.isClosed = True
        try:
            if self.writer.can_write_eof():
                self.writer.write_eof()
            self.writer.close()
        except:
            pass

    def __del__(self):

        self.logger.debug("Object is about to be deleted, performing cleanup...")

        try:
            self.close()
        except:
            pass

    def __str__(self):
        
        return "<Connection>"