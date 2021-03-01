import discord
from cmdsys import *

from core_models import BlockedChannel, AuditLogChannel, PinChannel

class ChannelBan(Command):

    class Add(AddModelCommand):

        MODEL = BlockedChannel
        FIELDS = {"channel_id": ChannelArgument}

    class Delete(DeleteModelCommand):

        MODEL = BlockedChannel
        FIELDS = {"channel_id": ChannelArgument}

    def setup(self):

        self.name = "cb"
        self.aliases.append("channelBan")
        self.aliases.append("chBan")
        self.desc = "Manage channel bans.\nAction can be either 'add' or 'delete'. If channel isn't specified, it defaults to the current channel."
        self.ownerOnly = True

        self.addSubcommand(self.Add())
        self.addSubcommand(self.Delete())

class ChannelLogs(Command):

    class Add(AddModelCommand):

        MODEL = AuditLogChannel
        FIELDS = {"channel_id": ChannelArgument}

    class Delete(DeleteModelCommand):

        MODEL = AuditLogChannel
        FIELDS = {"channel_id": ChannelArgument}

    def setup(self):

        self.name = "cal"
        self.aliases.append("channelAuditLog")
        self.aliases.append("chLog")
        self.desc = "Manage audit log channels.\nAction can be either 'add' or 'delete'. If channel isn't specified, it defaults to the current channel."
        self.permissions.administrator = True

        self.addSubcommand(self.Add())
        self.addSubcommand(self.Delete())

class ChannelsPin(Command):

    class Add(AddModelCommand):

        MODEL = PinChannel
        FIELDS = {"channel_id": ChannelArgument}

    class Delete(DeleteModelCommand):

        MODEL = PinChannel
        FIELDS = {"channel_id": ChannelArgument}

    def setup(self):

        self.name = "cp"
        self.aliases.append("channelPin")
        self.aliases.append("chPin")
        self.desc = "Manage pin channels.\nAction can be either 'add' or 'delete'. If channel isn't specified, it defaults to the current channel."
        self.permissions.administrator = True

        self.addSubcommand(self.Add())
        self.addSubcommand(self.Delete())