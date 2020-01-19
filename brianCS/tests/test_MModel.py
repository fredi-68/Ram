import unittest
import os
from .. import model

class TestModel(unittest.TestCase):

    def test_model_component_init(self):
        ttable = model.TokenTable()
        mmodel = model.MModel(6)
        tagger = model.PoSTagger()
        parser = model.Parser(ttable)

    def test_model_init(self):
        mmodel = model.BrianModel()

    def test_model_save_load(self):
        m = model.BrianModel()
        m.save("./test_model.zip")
        m.load("./test_model.zip")

    def test_model_train(self):
        m = model.BrianModel()
        with open("brianCS/training/megahal.trn") as f:
            m.train(map(lambda x: x.lower(), f.readlines()))

    def test_model_observe_respond(self):
        m = model.BrianModel()
        m.observe("hello world", "a conversation")
        res = m.respond("something completely different", "a conversation")
        self.assertEqual(res, "hello world") #since the model knows nothing else, this should be the output
        
    def tearDown(self):
        try:
            os.remove("./test_model.zip")
        except OSError:
            pass
