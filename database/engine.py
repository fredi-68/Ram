from typing import Type, TypeVar, Sequence, Mapping
from pathlib import Path
import logging

import sqlite3

from .models import Model
from .query import Query
from .filters import Filter
from .constraints import *
from .errors import DatabaseError
from .fields import EMPTY
from .transaction import Transaction

class DatabaseEngine():

    """
    Abstract DatabaseEngine interface.
    """

    def __init__(self):

        self.logger = logging.getLogger("database."+self.__class__.__name__)

    def connect(self, *args, **kwargs):

        """
        Connect to the database.
        """

        pass

    def disconnect(self, commit=True):

        """
        Disconnect from the database.
        if commit is True, any unwritten changes will be automatically committed before closing the connection.
        """

        pass

    def _create_model(self, model_cls: Type[Model]) -> str:

        """
        Create a table for this model.
        """

        pass

    def _query(self, model_cls: Type[Model], filters: Sequence[Filter]) -> str:

        """
        Query the database for models.
        model_cls is the Model subclass of the corresponding table.
        filters is a sequence of Filter instances applying restrictions to the query.
        returns a sequence fof Model instances.
        """

        pass

    def _insert(self, model: Model) -> str:

        """
        Insert a new Model instance into the database.
        """

        return model

    def _update(self, model: Model) -> str:

        """
        Update a Model instance on the database.
        """

        return model

    def _delete(self, model: Model) -> str:

        """
        Delete a Model isntance from the database.
        """

        pass

    def _bulk_delete(self, query: Query):

        """
        Bulk delete all records described by query.
        Implementing this method is OPTIONAL.
        """

        raise NotImplementedError()

    def _begin_transaction(self):

        """
        Begin a transaction.
        """

        pass

    def _end_transaction(self, rollback=False):

        """
        Commit a transaction.
        """

        pass

    def _execute(self, query: str, args: Sequence[object] = [], kwargs: Mapping[str, object] = []) -> None:

        pass

    def _fetch(self, model_cls: Type[Model]) -> Sequence[Model]:

        pass

    def _commit(self):

        """
        Commit any changes to the database.
        """

        pass

    def save(self, model: Model):

        """
        Save this model instance.
        Do not call this method directly. Call it on the model instance instead.
        """

        bound = model._bound
        query = self._update(model) if bound else self._insert(model)
        self._execute(query)
        model._bound = True

        if bound:
            self.on_update(model)
        else:
            self.on_insert(model)

    def delete(self, model: Model):

        """
        Delete this model instance.
        Do not call this method directly. Call it on the model instance instead.
        """

        self._execute(self._delete(model))
        model._bound = False

        self.on_delete(model)

    def fetch(self, query: Query) -> Sequence[Model]:

        """
        Execute a query on the database.
        Do not call this method directly. Instead, use DatabaseEngine.query() to create a query and use its execute() method.
        """

        self._execute(self._query(query._model, query._filters))
        return self._fetch(query._model)

    def query(self, model_cls: Type[Model]) -> Query:

        """
        Query the database for models.
        Returns a Query object which can be modified further to specify more query options.
        """

        return Query(self, model_cls)

    def new(self, model_cls: Type[Model]) -> Model:

        """
        Create a new model on the database.
        Returns a model instance.
        """

        model = model_cls()
        model.connect_engine(self)
        return model

    def register(self, model_cls: Type[Model]) -> None:

        """
        Register a Model class on the database.
        """

        query = self._create_model(model_cls)
        self._execute(query)

    def on_insert(self, model: Model):

        """
        Subclass hook for insert events.

        This method is called every time a model instance is inserted with the instance as a single argument.
        """

        pass

    def on_update(self, model: Model):

        """
        Subclass hook for update events.

        This method is called every time a model instance is updated in the database with the instance as a single argument.
        """

        pass

    def on_delete(self, model: Model):

        """
        Subclass hook for deletion events.

        This method is called every time a model instance is deleted from the database with the instance as a single argument.
        """

        pass

    def transaction(self) -> Transaction:

        """
        Start a SQL transaction.

        Returns a Transaction object which can be used as a context manager.
        """

        return Transaction(self)

    def bulk_delete(self, query: Query):

        try:
            self._execute(self._bulk_delete(query))
        except NotImplementedError as e:
            #fall back on simple delete
            for m in query:
                m.delete()

    def __del__(self):

        try:
            self.disconnect()
        except:
            pass

class SQLiteEngine(DatabaseEngine):

    def connect(self, path: Path, *args, **kwargs) -> bool:
        
        """
        Connect to a SQLite3 database.
        You can specify additional connection arguments, which will be passed to the sqlite3 database connector.
        """

        self._db = sqlite3.connect(path.as_posix(), *args, **kwargs)
        self._c = self._db.cursor()
        return True

    def disconnect(self, commit=True):
        
        if commit:
            self._commit()
        self._db.close()

    def _commit(self):
        
        return self._db.commit()

    def _fetch(self, model_cls):

        data = self._c.fetchall()
        models = []
        for row in data:
            model = model_cls()
            model.connect_engine(self)
            for field, value in zip(model._fields.values(), row):
                field._set_field(value)
            model._bound = True
            models.append(model)
        return models

    def _execute(self, query, args=[], kwargs={}):
        
        parameters = args or kwargs
        self.logger.debug("Executing query '%s' with arguments '%s'." % (query, repr(parameters)))
        self._c.execute(query, parameters)

    def _create_model(self, model_cls):
        
        fields = model_cls._fields

        #process fields
        field_specs = []
        for name, field in fields.items():
            field_constraints = []
            if not field._nullable:
                field_constraints.append("NOT NULL")
            if field._default is not None:
                field_constraints.append("DEFAULT %s" % field._serialize(field._default))
            for c in field._constraints:
                if isinstance(c, UniqueConstraint):
                    field_constraints.append("UNIQUE")
                elif isinstance(c, AIConstraint):
                    field_constraints.append("AUTOINCREMENT")
                elif isinstance(c, PKConstraint):
                    if len(model_cls._pk) < 2:
                        field_constraints.append("PRIMARY KEY")
                else:
                    raise DatabaseError("Constraint type '%s' is not supported by SQLite3 databases." % c.__class__.__name__)
            f = '"%s" %s %s' % (name, field._typeref, " ".join(field_constraints))
            field_specs.append(f)

        #process table
        table_constraints = []
        if len(model_cls._pk) > 1:
            table_constraints.append("PRIMARY KEY (%s)" % ", ".join(map(lambda x: '"%s"' % x, model_cls._pk)))

        #create query

        table_args = ", ".join([*field_specs, *table_constraints])
        return 'CREATE TABLE IF NOT EXISTS "%s" (%s);' % (model_cls._table_name, table_args)

    def _insert(self, model):
        
        field_names = []
        field_values = []
        for name, field in model._fields.items():
            value = field._get_field()
            if value is EMPTY:
                continue
            field_names.append(name)
            field_values.append(value)

        if not field_names:
            return 'INSERT INTO %s DEFAULT VALUES;' % model._table_name
        return 'INSERT INTO %s (%s) VALUES (%s);' % (model._table_name, ", ".join(field_names), ", ".join(field_values))

    def on_insert(self, model):

        # update the models values after insertion to retrieve generated values from the database
        # (for example defaults, expressions and auto increments).

        self._execute('SELECT * FROM %s WHERE ROWID=:id;' % model._table_name, kwargs={"id": self._c.lastrowid})
        for field, value in zip(model._fields.values(), self._c.fetchone()):
            field._set_field(value)

    def _update(self, model):
        
        update_args = []
        for name, field in model._fields.items():
            update_args.append("%s=%s" % (name, field._get_field()))
        return 'UPDATE %s SET %s;' % (model._table_name, ", ".join(update_args))

    def _delete(self, model):
        
        targets = []
        for pk in model._pk:
            targets.append(object.__getattribute__(model, pk)._get_field())

        delete_args = []
        for key, value in zip(model._pk, targets):
            delete_args.append("%s=%s" % (key, value))
        return 'DELETE FROM %s WHERE %s;' % (model._table_name, ", ".join(delete_args))

    def _query(self, model_cls, filters):
        
        select_args = ' AND '.join(map(lambda x: x.construct(), filters))

        if select_args:
            return 'SELECT * FROM %s WHERE %s;' % (model_cls._table_name, select_args)
        return 'SELECT * FROM %s;' % model_cls._table_name

    def _begin_transaction(self):
        
        self._execute("BEGIN TRANSACTION;")

    def _end_transaction(self, rollback=False):
        
        if rollback:
            self._execute("ROLLBACK TRANSACTION;")
        else:
            self._execute("COMMIT TRANSACTION;")