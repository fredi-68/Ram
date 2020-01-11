import discord
import logging

from audio import PCMSound

class FakeMessage():

    def __init__(self, content, author, channel):

        self.content = content
        self.author = author
        self.channel = channel

class ResponseManager():

    def __init__(self):

        self.logger = logging.getLogger("ResponseManager")
        self.is_closed=False

    def getMessage(self):

        """
        Returns the original message object.
        If the command was not issued through chat, this method will return None.
        """

        return None

    async def getCommand(self):

        """
        Returns the original command message. This will include the prefix of chat commands.
        If the command can not be determined this method will return an empty string.
        """

        return ""

    def getPermission(self):

        """
        Returns the permissions for the command issuer. For RPCs this will always be administrator level.
        If the permission level can not be determined this method will return a Permissions object with no permissions.
        """

        return discord.Permissions.none()

    def getID(self):

        """
        Returns the ID of the command issuer. For RPCs this will always be 1.
        If the ID can not be determined this method will return None
        """

        return None

    async def reply(self, msg, mention=False, flush_chat=True):

        """
        Send a response message to the command issuer.
        mention specifies if the targeted user should be mentioned and is
            ignored if the command was executed via RPC.
        Output is automatically buffered for RPC calls.
        If flush_chat is True, the message will be dispatched immediately. It is ignored for RPC calls.

        WARNING: Setting flush_chat to False will buffer messages until the ResponseManager is GCed OR another call to reply()
        is made with flush_chat set to True (in this case, all messages will be dispached in order).
        If you don't manually flush your messages at least once after setting flush_chat to False, they will be sent after an
        indefinite amount of time. If you sent messages with flush_chat=False, you should consider calling flush() to ensure that
        the messages are dispatched correctly.

        WARNING: If your message is longer than Discords internal character limit (currently 2000 characters per message) it
        may not send properly. The ResponseManager will attempt to split up messages that are longer than the character limit,
        however, this does not work in specific cases. For example, sending a message with a single line of more than 2000 characters
        will fail. Also, sending very long messages of over 5x the character limit may take severely longer due to Discord internal rate
        limiting. There is no way of cicumventing this behavior, so keep it short.

        If you try to send a message larger than 2000 characters a warning will be logged.
        """

        pass

    async def createEmbed(self, embed):

        """
        Send a response message to the command user using an Embed object.
        If the command was executed via RPC,
        embed behaviour will be emulated using ASCII characters.
        """

        pass

    def is_rpc(self):

        """
        Check if the message was send via RPC
        """

        return isinstance(self, RPCResponse)

    def is_chat(self):

        """
        Check if the message was send via chat
        """

        return isinstance(self, ChatResponse)

    async def flush(self):

        """
        Flushes the internal message buffer.
        For RPC, this is currently a no-op, as multipart messages are not implemented yet.
        """

        pass

    def close(self):

        """
        This method should always be called after the command has been executed, even in case of failure. If the command
        was issued by a RPC, this will accumulate all messages, send them to the caller and then close all streams and perform
        cleanup.
        It is safe to call this method more than once.
        This method is automatically called on object GC to make sure ressources get freed properly.
        """

        self.is_closed = True

    def __del__(self):

        #This can raise errors if the objects gets GCed while the interpreter is shutting down.
        #To prevent crashes after asyncio has shut down, we suppress any relevant errors this
        #call could raise since this is a clean up method and not that important
        try:
            self.logger.debug("Response handle is about to be destroyed, ensuring closed connections")
        except AttributeError:
            pass

        try:
            self.close()
        except:
            pass

class ChatResponse(ResponseManager):

    #Discord hard limits message length. For long responses, we want to automatically
    #split up the payload into chunks of the specified length.
    CHAT_CHARACTER_LIMIT = 2000

    def __init__(self, client, message):

        super().__init__()
        self.client = client
        self.msg = message

        self.messages = []

    async def getCommand(self):

        return self.msg.content

    def getMessage(self):
        
        return self.msg

    def getPermission(self):

        if self.msg.channel.type == discord.ChannelType.text:
            local_permissions = self.msg.author.permissions_in(self.msg.channel)
            try:
                server_permissions = self.msg.author.guild_permissions
            except:
                server_permissions = discord.Permissions.none()
            return discord.Permissions(local_permissions.value | server_permissions.value) #union both permissions
        #if everything fails, we return a safe permissions object without any permissions
        return discord.Permissions.none()

    def getID(self):

        return self.msg.author.id

    async def reply(self, msg, mention=False, flush_chat=True):

        if len(msg) > self.CHAT_CHARACTER_LIMIT:
            self.logger.warn("Message is over character limit, message may fail to send properly")

        for line in msg.split("\n"):
            await self._ChatReply(line, mention, False)
            mention = False #if mention was set, it will be in the first line, but no subsequent ones
        if flush_chat:
            await self._ChatReply("", False, True)

    async def _ChatReply(self, msg, mention, flush_chat):

        ret = self.msg.author.mention + ", " + msg if mention else msg #add a mention to the response if requested
        self.messages.append(ret)

        if flush_chat:

            #if we don't have any messages, exit
            while len(self.messages) > 0:
                ret = ""

                #if we run out of messages, finish this batch then exit
                while len(self.messages) > 0:

                    if len(ret) + len(self.messages[0]) > self.CHAT_CHARACTER_LIMIT:
                        if not ret: #This can happen when a single message is too large to be sent
                            #If this happens, it's the users fault, since we cannot split the message up
                            #without causing issues. We will attempt to send it but it WILL fail.
                            #Let the error propagate.
                            await self.msg.channel.send(self.messages.pop(0))
                        break

                    ret += self.messages.pop(0) #get next message and add it to the buffer.
                    ret += "\n" #add newline to separate messages
                                        #Don't go over the character limit

                #we want to avoid empty messages and always append a newline so we check for messages smaller than 2 characters
                ret = ret.rstrip("\n") #strip last newline
                if len(ret) > 0:
                    await self.msg.channel.send(ret) #send message

    async def createEmbed(self, embed):
        
        await self.msg.channel.send("", embed=embed)

    async def flush(self):

        """
        Flushes the internal message buffer.
        For RPC, this is currently a no-op, as multipart messages are not implemented yet.
        """

        await self.reply("", False, True) #flush the chat message buffer

    def close(self):
        
        if self.is_closed:
            return

        self.client.loop.create_task(self.flush()) #flush internal message buffer

        super().close()

class RPCResponse(ResponseManager):

    def __init__(self, reader, writer):

        super().__init__()
        self.reader = reader
        self.writer = writer

        self.messages = []

    async def getCommand(self):
        
        return (await self.reader.readline()).decode() #get command and convert it to str

    def getPermission(self):

        p = discord.Permissions.all() #Give RPC calls all permissions, regardless of accessed area
        return p

    def getID(self):

        return 1 #ensure compatability with chat commands

    async def reply(self, msg, mention=True, flush_chat=True):

        if not msg:
            return

        self.messages.append(msg)
        self.logger.info(msg) #log message to screen

    async def createEmbed(self, embed):
        
        title = str(embed.title)
        desc = str(embed.description)
        footer = str(embed.footer.text)
        author = str(embed.author.name)

        self.messages.append("Rich Embed:\n"+"="*60+"\n")
        self.messages.append("%s | %s\n" % (title, desc))
        for i in embed.fields:
            self.messages.append("\n"+i.name)
            self.messages.append("\n"+"-"*40)
            self.messages.append("\n"+i.value+"\n")

        if embed.footer != embed.Empty:
            self.messages.append("\n%s | %s" % (footer, author))

    def close(self):

        if self.is_closed:
            return

        #write response
        lines = map(str.encode, self.rpc_messages) #encode to bytes
        returnString = b" ".join(lines)
        if not returnString:
            returnString = b"Internal error: No response."
        try:
            self.writer.write(returnString)
        except IOError:
            self.logger.exception("IO Exception occured while trying to write RPC response:")
        #close RPC connection
        try:
            if hasattr(self.writer, "can_write_eof") and self.writer.can_write_eof():
                self.writer.write_eof() #close the stream the "nice" way
            else:
                self.logger.warning("Stream doesn't support write_eof()... this could lead to a hang in the RAT process")
            self.writer.close()
        except (IOError, OSError, AttributeError):
            self.logger.exception("Error occured while trying to close the RPC connection:")

        super().close()

class VoiceResponse(ResponseManager):

    def __init__(self, text, user, channel, tts, audio_manager):

        super().__init__()

        self.text = text
        self.user =  user
        self.channel = channel
        self.tts = tts
        self.audio_manager = audio_manager

    async def getCommand(self):

        return self.text

    def getMessage(self):

        return FakeMessage(self.text, self.user, self.channel)

    def getPermission(self):

        try:
            permissions = self.user.guild_permissions
        except:
            permissions = discord.Permissions.none()

        return permissions

    def getID(self):
        
        return self.user.id

    async def reply(self, msg, mention=False, flush_chat=True):

        s = await self.tts.synthesize(msg)
        sound = PCMSound(s)
        self.audio_manager.playSound(sound, self.channel, False)