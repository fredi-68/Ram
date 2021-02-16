from unittest import TestCase
from pathlib import Path
import logging

logging.basicConfig(level=logging.DEBUG)

from ..models import Model
from ..engine import SQLiteEngine
from ..fields import TextField, IntegerField, FloatField

DB_PATH = Path("test.db")

class TestModel(TestCase):

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

    def test_model_register(self):

        self.engine.register(self._Model)

    def test_model_insert(self):

        self.engine.register(self._Model)
        m = self.engine.new(self._Model)
        m.save()
        self.assertTrue(m._bound)

    def test_model_delete(self):

        self.engine.register(self._Model)
        m = self.engine.new(self._Model)
        m.save()
        self.assertTrue(m._bound)
        m.delete()
        self.assertFalse(m._bound)

    def test_model_query(self):

        self.engine.register(self._Model)
        m = self.engine.new(self._Model)
        m.save()
        m = self.engine.new(self._Model)
        m.test_int = 50
        m.save()
        
        models = self.engine.query(self._Model).filter(test_int=50)
        self.assertTrue(len(models) == 1)
        model = models[0]
        self.assertEqual(model.test_int, 50)
        self.assertEqual(model.test_float, None)
        self.assertEqual(model.test_string, "")

    def test_model_update(self):

        self.engine.register(self._Model)
        m = self.engine.new(self._Model)
        m.save()
        self.assertTrue(m._bound)
        m.test_string = "Hello World"
        m.save()