from unittest import TestCase
from pathlib import Path

from ..models import Model
from ..engine import SQLiteEngine
from ..fields import TextField, IntegerField, FloatField
from ..query import Query
from ..filters import Equals, And, Not
from ..errors import DatabaseError

DB_PATH = Path("test.db")

class TestFilters(TestCase):

    class _Model(Model):

        test_int = IntegerField(42)
        test_float = FloatField(null=True)
        test_string = TextField("", null=True)

    def setUp(self):

        self.engine = SQLiteEngine()
        self.engine.connect(DB_PATH)
        self.engine.register(self._Model)
        return super().setUp()

    def tearDown(self):

        self.engine.disconnect()
        DB_PATH.unlink()
        return super().tearDown()

    def test_filter_equals(self):

        m = self.engine.new(self._Model)
        m.test_int = 1
        m.test_float = 3.14
        m.test_string = "Hello World"
        m.save()

        self.assertEqual(len(self.engine.query(self._Model).filter(And(Equals("test_int", 1), Equals("test_float", 3.14)))), 1)

    def test_not(self):

        m = self.engine.new(self._Model)
        m.test_int = 1
        m.test_float = 3.14
        m.test_string = "Hello World"
        m.save()

        self.assertEqual(len(self.engine.query(self._Model).filter(Not(Equals("test_int", 2)))), 1)
        self.assertEqual(len(self.engine.query(self._Model).filter(Not(Equals("test_int", 1)))), 0)