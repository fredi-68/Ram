from .enums import OnConflict

class FieldConstraint():

    """
    Abstract base class for field constraints.
    """

    pass

class UniqueConstraint(FieldConstraint):

    """
    Constrain a fields value to be unique in this table.
    """

    def __init__(self, on_conflict=OnConflict.NOTHING):

        self.on_conflict = on_conflict

class PKConstraint(FieldConstraint):

    """
    Constrain a fields value to be uniquely identifying in this table.
    Using this constraint on a field will cause the database engine to declare an explicit primary key.
    May be used more than once, which will result in a composite primary key.
    """

    pass

class AIConstraint(FieldConstraint):

    """
    Constrain an integer field to automatically assign an incremental value.
    """

    pass