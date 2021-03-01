import shlex
from typing import Sequence, Callable
import json

from .errors import *

EMPTY = object()

class Field():

    """
    Abstract base class for model fields.
    """

    def __init__(self, typeref: str, default=None, null=False, constraints: Sequence["FieldConstraint"] = [], validators: Sequence[Callable] = []):

        """
        Create a new instance of Field.

        typeref is the datatype name as a string, as understood by SQL.
        default, if given, is the default value of this field.
        if null is True, this field may be set to null in the database.
        constraints is a sequence of FieldConstraints to use for this field.
        validators is a sequence of custom validators.
            Each validator is expected to be a callable accepting the value to be validated as its only argument.
        """

        self._typeref = typeref
        self._default = default
        self._nullable = null
        self._constraints = constraints
        self._validators = validators

        self._bound = False
        self._modified = False

        self._value = EMPTY

    def copy(self) -> "Field":

        return self.__class__(self._default, self._nullable, self._constraints, self._validators)

    def _validate(self, value):

        if not self.validate(value):
            raise ValidationError()
        for validator in self._validators:
            if not validator(value):
                raise ValidationError()

    def validate(self, value):

        """
        Custom validation hook.
        Override this if you want to implement custom validation for your fields.
        """

        return True

    def _deserialize(self, value):

        return value

    def _serialize(self, value):

        return str(value)

    def _get_field(self):

        if self._value is EMPTY:
            return EMPTY
        if self._value is None:
            return "NULL"
        self._validate(self._value)
        return self._serialize(self._value)

    def _set_field(self, value):

        if value is None:
            self._value = None
            return
        self._value = self._deserialize(value)

    def get_value(self):

        if self._value is EMPTY:
            return self._default
        return self._value

    def set_value(self, value):

        self._value = value
        self._modified = True

class TextField(Field):

    def __init__(self, *args, **kwargs):

        super().__init__("TEXT", *args, **kwargs)

    def _validate(self, value):

        if not isinstance(value, str):
            raise ValidationError("value must be a string, not %s" % value.__class__.__name__)
        super()._validate(value)

    def _serialize(self, value):

        if value == "":
            return '""'
        return shlex.quote(value)

class IntegerField(Field):

    def __init__(self, *args, **kwargs):

        super().__init__("INTEGER", *args, **kwargs)

    def _validate(self, value):
        
        if not isinstance(value, int):
            raise ValidationError("value must be an integer, not %s" % value.__class__.__name__)
        super()._validate(value)

    def _deserialize(self, value):
        
        return int(value)

class FloatField(Field):

    def __init__(self, *args, **kwargs):

        super().__init__("NUMBER", *args, **kwargs)

    def _validate(self, value):

        if not (isinstance(value, float) or isinstance(value, int)):
            raise ValidationError("value must be a float, not %s" % value.__class__.__name__)
        super()._validate(value)

    def _deserialize(self, value):
        
        return float(value)

class BooleanField(Field):

    def __init__(self, *args, **kwargs):

        super().__init__("NUMBER", *args, **kwargs)

    def _deserialize(self, value):
        return bool(value)

    def _serialize(self, value):
        return "1" if value else "0"

class JSONField(Field):

    def __init__(self, *args, **kwargs):

        super().__init__("TEXT", *args, **kwargs)

    def _validate(self, value):

        if not isinstance(value, dict):
            if isinstance(value, list):
                raise ValidationError("Cannot serialize list objects, only dict.")
            raise ValidationError("value must be a dict, not %s" % value.__class__.__name__)
        super()._validate(value)

    def _serialize(self, value):

        return shlex.quote(json.dumps(value))

    def _deserialize(self, value):
        
        return json.loads(value)