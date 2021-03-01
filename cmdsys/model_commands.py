import logging
import asyncio
import discord
import json

from collections import defaultdict
from typing import Type, List, Dict, Any, DefaultDict, Callable

from database import Model, ValidationError, Equals
from database.fields import *
from database.engine import DatabaseEngine

from .errors import InvalidConfigException
from ._globals import environment
from .abcs import *
from .arguments import *

class _ModelCommand(Command):

    """
    Abstract base class for managing database models.

    The aim of this set of commands is to simplify the development of
    management commands for database models by abstracting much of the boilerplate
    code. The user instead specifies the model and the fields they wish to expose
    through the command. The command itself, including all arguments is then 
    automatically generated.
    """

    MODEL: Type[Model] = None
    DB: Any = None
    NAME: str = None
    FIELDS: Dict[str, Type[Argument]] = {}

    _FIELD_MAP: DefaultDict[Type[Field], Type[Argument]] = defaultdict(lambda x: StringArgument, {
        TextField: StringArgument,
        IntegerField: IntArgument,
        FloatField: FloatArgument,
        BooleanField: BoolArgument
    })

    def setup(self):
        
        if self.MODEL is None:
            raise InvalidConfigException("Must specify a model when creating an ORM managment command.")
        if not issubclass(self.MODEL, Model):
            raise InvalidConfigException("Model must be a subclass of database.models.Model, not %s." % self.MODEL.__class__.__name__)

        #setup command
        if self.NAME is None:
            self.name = self.MODEL.__name__
        else:
            self.name = self.NAME

        #setup arguments
        for f_name, a_type in self.FIELDS.items():
            field = self.MODEL._fields[f_name]
            if a_type is None:
                a_type = self._FIELD_MAP[field.__class__]
                self.logger.debug("Auto-configuring field '%s' as type '%s'." % (f_name, a_type.__name__))
            self.addArgument(a_type(f_name))

        # Turn this off because we can only handle naive data models.
        # If you need delimiters, consider writing your own management commands.
        self.allowDelimiters = False 

    def get_db(self) -> DatabaseEngine:

        """
        Return the appropriate database engine for the current context.
        """

        if self.DB is None:
            return environment.database.get_db_by_message(self.msg)
        return environment.database.get_db(self.DB)

    def args_to_kwargs(self, args, kwargs) -> dict:
        
        new = {}
        new.update(kwargs)
        args = list(args)
        for i in self.arguments:
            if i.optional:
                continue
            new[i.name] = args.pop(0)
        return new

class AddModelCommand(_ModelCommand):

    NAME = "add"

    async def call(self, *args, **kwargs):

        kwargs = self.args_to_kwargs(args, kwargs)

        db = self.get_db()
        m = db.new(self.MODEL)
        for name, value in kwargs.items():
            if hasattr(value, "id"):
                value = value.id
            try:
                setattr(m, name, value)
            except (NameError, KeyError) as e:
                await self.respond("Could not create new %s instance: Property %s does not exist." % (self.MODEL.__name__, name), True)
                return
            except (ValueError, ValidationError) as e:
                await self.respond("Could not create new %s instance: Value for property %s outside acceptable ranges: %s" % (self.MODEL.__name__, name, str(e)), True)
                return
            except TypeError as e:
                await self.respond("Could not create new %s instance: Wrong type for field %s: %s" % (self.MODEL.__name__, name, value.__class__.__name__), True)
                return
            except Exception as e:
                await self.respond("Could not create new %s instance: %s" % (self.MODEL.__name__, str(e)), True)
                return
        try:
            m.save()
        except ValidationError as e:
            await self.respond("Unable to save new %s instance: Invalid value specified: %s" % (self.MODEL.__name__, str(e)), True)
            return
        except DatabaseError as e:
            await self.respond("Unable to save new %s instance: Database error: %s" % (self.MODEL.__name__, str(e)), True)
            return
        except Exception as e:
            await self.respond("Unable to save new %s instance: An unknown exception occured: %s" % (self.MODEL.__name__, str(e)), True)
            return

        await self.respond("Successfully created new instance of %s." % self.MODEL.__name__)

class DeleteModelCommand(_ModelCommand):

    NAME = "delete"

    async def call(self, *args, **kwargs):

        kwargs = self.args_to_kwargs(args, kwargs)

        db = self.get_db()
        q = db.query(self.MODEL)

        for name, value in kwargs.items():
            if hasattr(value, "id"):
                value = value.id
            q.filter(Equals(name, value))

        try:
            q.delete()
        except DatabaseError as e:
            await self.respond("Unable to delete %s record(s): Database error: %s" % (self.MODEL.__name__, str(e)), True)
            return
        except Exception as e:
            await self.respond("Unable to delete %s record(s): An unknown exception occured: %s" % (self.MODEL.__name__, str(e)), True)
            return

        await self.respond("Successfully deleted %s record(s)." % self.MODEL.__name__)