from database import Model
from database import TextField, IntegerField, BooleanField
from database import PKConstraint

"""
Define some core database models used by the bot.

If you need your own models for your command you should consider
declaring them inside your command file instead.
"""

class BlockedUser(Model):

    user_id = IntegerField(constraints=[PKConstraint()])

class BlockedChannel(Model):

    channel_id = IntegerField(constraints=[PKConstraint()])

class PinChannel(Model):

    channel_id = IntegerField(constraints=[PKConstraint()])

class AuditLogChannel(Model):

    channel_id = IntegerField(constraints=[PKConstraint()])

class TimeoutRole(Model):

    role_id = IntegerField(constraints=[PKConstraint()])

class TimeoutCount(Model):

    user_id = IntegerField(constraints=[PKConstraint()])
    count = IntegerField()

class PinReactionSettings(Model):

    count = IntegerField()
    emote = TextField()
    needs_mod = BooleanField()