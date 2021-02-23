from pathlib import Path
import logging
from weakref import WeakValueDictionary
import os
from typing import Any, Type, Union

from discord import Message

from .engine import DatabaseEngine, SQLiteEngine
from .models import Model

class DatabaseManager():

    """
    Database engine manager class.

    This class handles access to the database layer by directing requests to
    the appropriate engine instance depending on the callers location.
    Typically this is done by looking at the guild ID of a commands invoking
    message.
    If you need to use a global object store accessible anywhere, it is a
    good convention to request the database with the name "global". However,
    databases may be arbitrarily named. 
    """

    logger = logging.getLogger("database.DatabaseManager")

    def __init__(self, path: Union[Path, str], engine: DatabaseEngine = SQLiteEngine):

        """
        Create a new instance of DatabaseManager.
        path is the path to the location where the databases should be stored.
            It may be a path to a physical disk location or a URI pointing to a network resource.
        engine is the class of the DatabaseEngine to use.
        """

        self._path = path
        self._cache = WeakValueDictionary()
        self._engine = engine
        self._registered_models = set()

        if isinstance(self._path, Path) and not self._path.exists():
            os.makedirs(self._path, exist_ok=True)

    def register_model(self, model: Type[Model]):

        """
        Register a model on this DatabaseManager.
        Registering a model on a DatbaseManager is similar to registering it on a DatabaseEngine.
        Any model registered on a DatabaseManager will be automatically registered on any DatabaseEngine
        subsequently requested or created.

        If the model is already registered on this DatabaseManager, this method does nothing.
        """

        if not model in self._registered_models:
            self._registered_models.add(model)

    def get_db(self, id: Any) -> DatabaseEngine:

        """
        Load the database for the specified ID and return an instance of DatabaseEngine.
        The exact type returned depends on the DatabaseEngine subclass passed to the constructor.
        Will create database if it doesn't exist.
        """

        id = str(id)
        try: #perform cache lookup for this server
            ref = self._cache[id] 
            return ref
        except KeyError: #the object may have been garbage collected while we were referencing it, or just doesn't exist
            pass

        # register models
        handle = self._engine(self.path / id)
        for model in self._registered_models:
            handle.register(model)
            
        self._cache[id] = handle #cache our engine instance
        return handle

    def get_db_by_message(self, msg: Message = None) -> DatabaseEngine:

        """
        Like get_db(), but accepts discord.Message objects instead of strings.
        This method will load and return the database corresponding to the server the message
        was posted in.
        If the message was posted in a private/group channel instead, or wasn't specified at all,
        this method will return the "global" database instead for convenience.
        """

        if msg is not None:
            if msg.guild:
                return self.getServer(msg.guild.id)

        #fall back to global database for DMs and unspecified messages
        return self.getServer("global")
