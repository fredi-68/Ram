import unittest
from unittest.mock import Mock
from asyncio import AbstractEventLoop

from discord import Client, Message

import interaction

TEST_SCRIPT = """
//This is a test script.
//It will make use of all the features supported by CIDSL and ensure it doesn't produce any errors or faulty output.

//Set a local variable
set myVar_1 -> "World"

//Use variable substitution
set myVar_2 -> "Hello %myVar_1"

//Register a logging handle
log 20 -> myVar_2

//Create a condition, store it in a name
set myCondition -> (#"hello", #"world")

//Register a responder
on #"hello" -> myVar_2
"""

class TestCIDSL(unittest.TestCase):

    def test_cidsl_compile(self):

        with self.subTest("init interaction") as c:
            interaction.init()

        client = Mock(spec=Client)
        loop = Mock(AbstractEventLoop)
        client.loop = loop
        msg = Mock(spec=Message)
        msg.content = "Hello World"

        parser = interaction.DSLParser()
        tokenGen = parser.parse(TEST_SCRIPT)
        interpreter = interaction.DSLInterpreter(client)
        interpreter.compile(tokenGen)

        interpreter.run(msg)
        
        msg.channel.send.assert_called_with("%s, Hello World" % msg.author.mention)
