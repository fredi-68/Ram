class Transaction:

    """
    SQL transaction context manager.

    Do not instatiate this class directly.
    Use DatabaseEngine.transaction() instead.
    """

    def __init__(self, engine: "DatabaseEngine"):

        self.engine = engine

    def __enter__(self):

        self.engine._begin_transaction()

    def __exit__(self, exc_type, exc_value, tb):

        if exc_type is not None:
            self.engine._end_transaction(True)
        else:
            self.engine._end_transaction(False)
        return False