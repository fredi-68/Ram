from .errors import *
from .fields import Field, IntegerField
from .constraints import PKConstraint, AIConstraint

class _ModelMeta(type):

    """
    Metaclass for Models.

    Perform some basic preprocessing on fields.
    """

    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):
        return {}

    def __new__(cls, name, bases, namespace, **kwargs):

        fields = {}
        pk = []
        for key, value in namespace.items():
            if isinstance(value, Field):
                fields[key] = value
                for constraint in value._constraints:
                    if isinstance(constraint, PKConstraint):
                        pk.append(key)

        if not pk:
            #construct artificial PK
            id = IntegerField(null=False, constraints=(PKConstraint(), AIConstraint()))
            namespace["id"] = id
            pk.append("id")
            fields["id"] = id

        namespace["_fields"] = fields
        namespace["_pk"] = pk
        namespace["_table_name"] = name
        return type.__new__(cls, name, bases, dict(namespace))

class Model(metaclass=_ModelMeta):

    def __init__(self):

        """
        Create a new Model instance.
        Do not call this method yourself. To create instances of Models, use a DatabaseEngine instead.
        """

        self._bound = False
        self._engine = None

        #copy fields to prevent issues with dangling values
        for k, f in self._fields.items():
            new_field = f.copy()
            object.__setattr__(self, k, new_field)
            self._fields[k] = new_field

    def connect_engine(self, engine: "DatabaseEngine"):

        """
        Connect a database engine to this model.
        Do not call this method yourself. Use the new() method of a DatabaseEngine instead.
        """

        self._engine = engine

    def _validate(self):

        """
        Internal validation handler.
        """

        if not self.validate():
            raise ValidationError()

    def validate(self):

        """
        Custom validation hook.
        Override this method if you wish to implement custom validation for your model.
        """

        return True

    def delete(self):

        """
        Delete this record from the database.
        Model instance must be bound.
        """

        if not self._bound:
            raise UnboundDataException("Trying to perform database operation on unbound instance of %s" % self.__class__.__name__)

        self._engine.delete(self)

    def save(self):

        """
        Save this record to the database.
        This will execute either an insert or an update query depending on the state of the model.
        """

       
        if self._engine is None:
            raise UnboundDataException("Cannot execute insert/update operation without a valid DatabaseEngine instance.")
        self._validate()
        self._engine.save(self)

    def __getattribute__(self, name: str):

        if name in object.__getattribute__(self, "_fields"):
            return object.__getattribute__(self, name).get_value()
        return object.__getattribute__(self, name)

    def __setattr__(self, name: str, value: object):

        if name in self._fields:
            return object.__getattribute__(self, name).set_value(value)
        return object.__setattr__(self, name, value)

    def __eq__(self, value):
        
        if not isinstance(value, self.__class__):
            return False
        for f in self._fields:
            if getattr(self, f) != getattr(value, f):
                return False
        return True