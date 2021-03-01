import discord

from chatutils import getChannelMention, getMention, getRoleMention, getRole

from .errors import ArgumentException, CommandCallAbortedException
from .utils import dialogReact
from .abcs import Argument

class StringArgument(Argument):

    async def parse(self, client, argument, response_handle, command):
        
        return argument

class IntArgument(Argument):

    async def parse(self, client, argument, response_handle, command):
        
        return int(argument)

class FloatArgument(Argument):

    async def parse(self, client, argument, response_handle, command):
        
        return float(argument)

class BoolArgument(Argument):

    async def parse(self, client, argument, response_handle, command):
        
        if argument in ("True", "true", "1"):
            return True
        elif argument in ("False", "false", "0"):
            return False

        raise ArgumentException("Type bool expected, but got %s." % argument)

class MessageArgument(Argument):

    async def _parse_react(self, client, response_handle):

        msg = await dialogReact(response_handle.getMessage().channel, response_handle.getMessage().author, client, "Please react to the message you are trying to select with an emoji of your choice.")
        if not msg:
            raise CommandCallAbortedException("User did not respond to reaction request.")
        return msg

    async def _parse_delimiter(self, client, argument, response_handle):

        channel_id, message_id = list(map(int, argument.split(":", 1)))
        try:
            msg = await client.get_channel(channel_id).fetch_message(message_id)
        except:
            raise ArgumentException("Could not find message for delimiter expression %s." % argument)

        return msg

    async def parse(self, client, argument, response_handle, command):
        
        if argument == "react":
            if not response_handle.is_chat():
                raise ArgumentException("react selectors are only available in chat.")
            return await self._parse_react(client, response_handle)

        if ":" in argument:
            if not command.allowDelimiters:
                raise ArgumentException("Delimiters are not allowed by this command.")
            return await self._parse_delimiter(client, argument, response_handle)

        if not response_handle.is_chat():
            raise ArgumentException("Must specify a channel when selecting a message from console.")
        try:
            return await response_handle.getMessage().channel.fetch_message(int(argument))
        except:
            raise ArgumentException("%s is not a valid message ID." % argument)

class ChannelArgument(Argument):

    async def _parse_post(self, client, response_handle):

        await response_handle.reply("Please post a message in the channel you are trying to select. It will be automatically deleted.")
        message = await client.wait_for_message(author=response_handle.getMessage().author, timeout=30)
        if not message:
            raise CommandCallAbortedException("User did not respond to post select request.")
        channel = message.channel
        try:
            await client.delete_message(message) #get rid of the message the user posted to select
        except discord.HTTPException:
            pass
        return channel

    async def parse(self, client, argument, response_handle, command):

        if argument == "post":
            if not response_handle.is_chat():
                raise ArgumentException("post selectors are only available in chat.")
            return await self._parse_post(client, response_handle)

        m = getChannelMention(argument)
        if m:
            argument = m

        return await client.fetch_channel(int(argument))

class ServerArgument(Argument):

    async def parse(self, client, argument, response_handle, command):

        return await client.fetch_guild(int(argument))

class MemberArgument(Argument):

    async def _parse_delimiter(self, client, argument, response_handle):

        guild_id, member_id = argument.split(":", 1)
        try:
            member = await (await client.fetch_guild(guild_id)).fetch_member(member_id)
        except:
            raise ArgumentException("Could not find member for delimiter expression %s." % argument)

        return member

    async def parse(self, client, argument, response_handle, command):

        if ":" in argument:
            if not command.allowDelimiters:
                raise ArgumentException("Delimiters are not allowed by this command.")
            return await self._parse_delimiter(client, argument, response_handle)

        m = getMention(argument)
        if m:
            argument = m

        return await response_handle.getMessage().guild.fetch_member(argument)

class UserArgument(Argument):

    async def parse(self, client, argument, response_handle, command):
        
        m = getMention(argument)
        if m:
            argument = m

        argument = int(argument)

        return await client.fetch_user(argument)

class RoleArgument(Argument):

    async def _parse_delimiter(self, client, argument, response_handle):

        server_id, role_id = argument.split(":", 1)
        try:
            return (await client.fetch_guild(server_id)).get_role(role_id)
        except:
            raise ArgumentException("Could not find role for delimiter expression %s." % argument)

    async def parse(self, client, argument, response_handle, command):
        
        if ":" in argument:
            if not command.allowDelimiters:
                raise ArgumentException("Delimiters are not allowed by this command.")
            return await self._parse_delimiter(client, argument, response_handle)

        m = getRoleMention(argument)
        if m:
            argument = m
        
        return getRole(response_handle.getMessage().guild, argument)