from typing import List, Type

from .errors import DatabaseError
from .filters import Equals

class Query():

    """
    Class for executing queries against a database.

    A query is linked to a database Model and allows sequential filtering to be performed on its records.
    The Query class supports a fluent interface for applying various Filters to a database query.
    Queries evaluate lazily, meaning that a query is only executed once its data is actually requested by
    the client code. Filtering a query does not require the database to be accessed.
    """

    def __init__(self, database_engine: "DatabaseEngine", model: Type["Model"]):

        self._engine = database_engine
        self._model = model
        self._filters: List["Filter"] = []

        self._result: List["Model"] = []

        self._executed = False

    def _ensure_executed(self):

        """
        Helper method.
        This will execute the query if it has not already been executed.
        """

        if self._executed:
            return 

        self.execute()
        self._executed = True

    def execute(self):

        """
        Execute this query immediately.
        If this query was already executed, DatabaseError will be raised.
        """

        if self._executed:
            raise DatabaseError("Cannot re-execute an already executed query.")
        self._result = self._engine.fetch(self)
        self._executed = True

    def filter(self, _filter: "Filter" = None, **kwargs) -> "Query":

        """
        Apply a Filter to this query.
        Returns this query instance.
        """

        if _filter and kwargs:
            raise RuntimeError("Specifying both Filter and kwargs is not allowed.")

        if self._executed:
            raise DatabaseError("Cannot filter a database query that has already been executed.")
        else:
            if _filter is not None:
                self._filters.append(_filter)
            else:
                for field, value in kwargs.items():
                    self._filters.append(Equals(self._model._fields[field], field, value))
        return self

    def delete(self):

        """
        Shortcut method for deleting all entries matching this query.
        """
        
        self._ensure_executed()
        self._engine.bulk_delete(self)
        
    def __iter__(self):

        self._ensure_executed()
        return iter(self._result)

    def __len__(self) -> int:

        self._ensure_executed()
        return len(self._result)

    def __getitem__(self, key: str) -> "Model":

        self._ensure_executed()
        return self._result[key]

    def __contains__(self, model: "Model") -> bool:

        self._ensure_executed()
        for m in self._result:
            if m == model:
                return True
        return False