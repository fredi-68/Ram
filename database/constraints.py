from .enums import OnConflict

class FieldConstraint():

    pass

class UniqueConstraint(FieldConstraint):

    def __init__(self, on_conflict=OnConflict.NOTHING):

        self.on_conflict = on_conflict

class PKConstraint(FieldConstraint):

    pass

class AIConstraint(FieldConstraint):

    pass