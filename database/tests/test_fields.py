from unittest import TestCase
from pathlib import Path

from ..models import Model
from ..engine import SQLiteEngine
from ..fields import IntegerField, TextField, FloatField, JSONField

DB_PATH = Path("test.db")

class TestInt(TestCase):

    def setUp(self):

        self.engine = SQLiteEngine()
        self.engine.connect(DB_PATH)
        return super().setUp()

    def tearDown(self):

        self.engine.disconnect()
        DB_PATH.unlink()
        return super().tearDown()

    def test_int_init(self):

        class M(Model):

            int_base = IntegerField()
            int_default = IntegerField(default=42)
            int_null = IntegerField(null=True)

        self.engine.register(M)
        m = self.engine.new(M)
        with self.assertRaises(Exception):
            m.save()
        m.int_base = 99
        m.save()

class TestText(TestCase):

    def setUp(self):

        self.engine = SQLiteEngine()
        self.engine.connect(DB_PATH)
        return super().setUp()

    def tearDown(self):

        self.engine.disconnect()
        DB_PATH.unlink()
        return super().tearDown()

    def test_text_init(self):

        class M(Model):

            text_base = TextField()
            text_default = TextField(default="Hello World")
            text_null = TextField(null=True)

        self.engine.register(M)
        m = self.engine.new(M)
        with self.assertRaises(Exception):
            m.save()
        m.text_base = "Something Else"
        m.save()

class TestFloat(TestCase):

    def setUp(self):

        self.engine = SQLiteEngine()
        self.engine.connect(DB_PATH)
        return super().setUp()

    def tearDown(self):

        self.engine.disconnect()
        DB_PATH.unlink()
        return super().tearDown()

    def test_float_init(self):

        class M(Model):

            float_base = FloatField()
            float_default = FloatField(default=3.14)
            float_null = FloatField(null=True)

        self.engine.register(M)
        m = self.engine.new(M)
        with self.assertRaises(Exception):
            m.save()
        m.float_base = 99.9999
        m.save()

class TestJSON(TestCase):

    def setUp(self):

        self.engine = SQLiteEngine()
        self.engine.connect(DB_PATH)
        return super().setUp()

    def tearDown(self):

        self.engine.disconnect()
        DB_PATH.unlink()
        return super().tearDown()

    def test_json_init(self):

        class M(Model):

            dict_base = JSONField()
            dict_default = JSONField(default={"some_key": "hi"})
            dict_null = JSONField(null=True)

        self.engine.register(M)
        m = self.engine.new(M)
        with self.assertRaises(Exception):
            m.save()
        m.dict_base = {"Hello World": 12345}
        m.save()