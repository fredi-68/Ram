from unittest import TestCase
from pathlib import Path

from ..models import Model
from ..engine import SQLiteEngine
from ..fields import TextField, IntegerField, FloatField

DB_PATH = Path("test.db")

class TestEngine(TestCase):

    class _Model(Model):

        test_int = IntegerField(42)
        test_float = FloatField(null=True)
        test_string = TextField("", null=True)

    def setUp(self):

        self.engine = SQLiteEngine()
        self.engine.connect(DB_PATH)
        return super().setUp()

    def tearDown(self):

        self.engine.disconnect()
        DB_PATH.unlink()
        return super().tearDown()

    def test_transactions(self):

        self.engine.register(self._Model)
        with self.engine.transaction() as t:
            m = self.engine.new(self._Model)
            m.save()