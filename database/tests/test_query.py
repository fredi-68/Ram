from unittest import TestCase
from pathlib import Path

from ..models import Model
from ..engine import SQLiteEngine
from ..fields import TextField, IntegerField, FloatField
from ..query import Query
from ..filters import Equals
from ..errors import DatabaseError

DB_PATH = Path("test.db")

class TestQUery(TestCase):

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

    def test_query(self):

        q = self.engine.query(self._Model)
        self.assertIsInstance(q, Query)

    def test_query_filter_implicit(self):

        self.engine.query(self._Model).filter(test_int=10).execute()

    def test_query_filter_explicit(self):

        self.engine.query(self._Model).filter(Equals("test_int", 10)).execute()

    def test_query_multiple_execute(self):

        q = self.engine.query(self._Model)
        q.execute()
        with self.assertRaises(DatabaseError):
            q.execute()

    def test_query_iterator(self):

        q = self.engine.query(self._Model)
        it = iter(q)
        self.assertTrue(hasattr(it, "__next__"))

    def test_query_bool(self):

        q = self.engine.query(self._Model)
        self.assertFalse(q)
        self.engine.new(self._Model).save()
        q = self.engine.query(self._Model)
        self.assertTrue(q)

    def test_query_contains(self):

        m = self.engine.new(self._Model)
        q = self.engine.query(self._Model)
        self.assertFalse(m in q)
        m.save()
        q = self.engine.query(self._Model)
        self.assertTrue(m in q)

    def test_query_index(self):

        m = self.engine.new(self._Model)
        q = self.engine.query(self._Model)
        with self.assertRaises(IndexError):
            q[0]
        m.save()
        q = self.engine.query(self._Model)
        self.assertEqual(q[0], m)