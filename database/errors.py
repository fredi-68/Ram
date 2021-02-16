class DatabaseError(BaseException):

    pass

class IntegrityError(DatabaseError):

    pass

class ValidationError(DatabaseError):

    pass

class UnboundDataException(DatabaseError):

    pass