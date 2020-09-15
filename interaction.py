#Discord ProtOS Bot
#
#Author: fredi_68
#
#Chat interaction based on hardcoded text responses | Quotes | CIDSL

import random
import os
import logging
import re
import asyncio

import discord

from audio import FFMPEGSound

BASE_PATH = "chat/"

logger = logging.getLogger("Interaction")

PRIVILEGE_WORDS = {
    "black":4,
    "croissant":2,
    "waitrose":5,
    "brunch":2,
    "avocado":1,
    "quinoa":2,
    "brioche":2
    }

def init():

    global mentioned
    global greet
    global agree
    global disagree
    global confused
    global confirm
    global denied
    global goodnight

    logger.info("Loading chat lines...")
    mentioned = lineStorage(BASE_PATH+"responses/mentioned.txt")
    greet = lineStorage(BASE_PATH+"responses/greet.txt")
    agree = lineStorage(BASE_PATH+"responses/agree.txt")
    disagree = lineStorage(BASE_PATH+"responses/disagree.txt")
    confused = lineStorage(BASE_PATH+"responses/confused.txt")
    confirm = lineStorage(BASE_PATH+"responses/confirm.txt")
    denied = lineStorage(BASE_PATH+"responses/denied.txt")
    goodnight = lineStorage(BASE_PATH+"responses/goodnight.txt")
    logger.info("Loading done.")

def calculatePrivilegePoints(msg):

    """Calculate the amount of privilege points one should receive from a message."""

    totalScore = 0
    wordCount = 0
    for item in PRIVILEGE_WORDS.items():
        words = msg.lower().count(item[0])
        wordCount += words
        totalScore += words*item[1]
    if totalScore < 1:
        return 0
    return int(totalScore/(wordCount/2))

class lineStorage():

    logger = logging.getLogger("LineStorage")

    def __init__(self, path, name=None):
        
        """Manages a file filled with phrases and provides access to such.
        Each phrase should occupy a single line. Empty lines will be automatically removed."""

        self.path = path
        if not name:
            self.name = path
        else:
            self.name = name
        self.lines = []
        self.load()

    def load(self):

        """Load lines from storage file."""

        try:
            f = open(self.path)
        except:
            return False

        self.lines = list(map(lambda x: x.rstrip("\n"), f.readlines()))
        f.close()

    def getRandom(self):

        """Returns a random line from memory."""

        try:
            return random.choice(self.lines)
        except IndexError: #empty sequence?
            return ""

    def getLine(self, index):

        """Returns the line at index from memory. If the line doesn't exist, the returned value will be an empty string."""

        if not isinstance(index,int) or index >= len(self.lines) or index < 0:
            return "" #if the line doesn't exist fail silently
        return self.lines[index]

    def addLine(self, line):

        """Add a line to the internal line storage. This will also write the entire line storage to the filesystem. Used by the quote subsystem.
        If the operation was successfull, the returned value will be the index of the newly created line."""

        try:
            f = open(self.path, "w")
        except:
            return False

        self.lines.append(line)

        #refresh storage file
        for i in self.lines:
            if i: #make sure empty line don't make it into storage
                f.write(i.rstrip("\n")+"\n") #make sure only ONE newline remains
        f.close()

        return self.lines.index(line)

class QuoteManager():

    logger = logging.getLogger("QuoteManager")

    def __init__(self, path="chat/quotes/"):

        """Manages a set of files representing quote line storages for users."""

        self.path = path
        self.files = {}
        self.load()

    def load(self, path=None):

        """Load all quote files from a directory."""

        if path is not None:
            self.path = path
        os.makedirs(self.path, exist_ok=True) #ensure directory exists
        for i in os.listdir(self.path):
            name = i.rsplit(".",1)[0]
            self.files[name] = lineStorage(self.path+i,name)
        return

    def getQuote(self, name, index):

        """Get the quote at index for the given name. If the name doesn't exist, the returned value will be None. If the index doesn't exist, the returned value will be an empty string."""

        if not name in self.files.keys():
            return None
        q = self.files[name].getLine(index)
        if not q:
            return ""
        return '"'+q+'" -'+name

    def getRandomByName(self, name):

        """Get a random quote for the given name. If the name doesn't exist, the returned value will be None."""

        if not name in self.files.keys():
            return None
        return '"'+self.files[name].getRandom()+'" -'+name

    def getRandom(self):

        """Get a random quote for a random name. If no names are known to the system, the returned value will be None."""

        if len(self.files) < 1: #random.choice fails otherwise
            return None
        file = self.files[random.choice(list(self.files.keys()))]
        return '"'+file.getRandom()+'" -'+file.name

    def addFile(self, name):

        """Try to add a new file for the given name. If the file was created, the returned value will be True."""

        try:
            f = open(self.path+name+".txt","w")
            f.close()
            self.files[name] = lineStorage(self.path+name+".txt",name)
        except:
            return False
        return True

    def addQuote(self, name, line):

        """Try to add a new quote for the given name. If the file for the line storage doesn't exist, this method will try to create it.
        If the line was added successfully, the returned Value will be the index of the newly created quote."""

        if not name in self.files.keys():
            if not self.addFile(name):
                return False
        if not line:
            return #make sure empty line don't make it into storage
        return self.files[name].addLine(line)

#CIDSL STUFF

class DSLType:

    def __init__(self, value):

        self.value = value

class TActionSeparator(DSLType):

    pass

class DynamicType(DSLType):

    def __init__(self):

        pass

    def evaluate(self, message, globals, locals):

        pass

    def resolveType(self, var, message, globals, locals):

        if isinstance(var, DynamicType):
            return var.evaluate(message, globals, locals) #resolve dynamic types
        elif isinstance(var, DSLType):
            return var.value
        return var

class TString(DynamicType):

    def __init__(self, value):

        self.value = value

    def evaluate(self, message, globals, locals):
        
        s = self.resolveType(self.value, message, globals, locals)
        output = []
        while s.find("%") > -1:
            substr = s.split("%", 1)
            output.append(substr[0])
            if substr[1][0] == "%": #literal %
                output.append("%")
                s = substr[1][1:]
                continue
            name = substr[1].split(" ", 1)
            if not name[0]: #also literal %
                output.append("%")
                s = name
                continue
            var = name[0]
            if var in locals:
                var = locals[var]
            elif var in globals:
                var = globals[var]
            else:
                raise RuntimeError("Name '"+var+"' is not defined!")

            output.append(str(self.resolveType(var, message, globals, locals)))
            if len(name) > 1:
                s = name[1]
                continue
            s = ""
            break
        output.append(s)
        return "".join(output)

class TInversion(DynamicType):

    def __init__(self, expression):

        self.expression = expression

    def evaluate(self, message, globals, locals):

        return not self.resolveType(self.expression, message, globals, locals)

class TSubstring(DynamicType):

    def __init__(self, value):

        self.value = value

    def evaluate(self, message, globals, locals):

        return self.resolveType(self.value, message, globals, locals).lower() in message.content.lower()

class TConditionAnd(DynamicType):

    def __init__(self, *expressions):

        self.expressions = expressions

    def evaluate(self, message, globals, locals):

        for i in self.expressions:
            if not self.resolveType(i, message, globals, locals):
                return False
        return True

class TConditionOr(DynamicType):

    def __init__(self, *expressions):

        self.expressions = expressions

    def evaluate(self, message, globals, locals):

        for i in self.expressions:
            if self.resolveType(i, message, globals, locals):
                return True
        return False

class TName(DynamicType):

    def __init__(self, name):

        self.name = name

    def evaluate(self, message, globals, locals):

        value = None
        if self.name in locals:
            value = locals[self.name]
        elif self.name in globals:
            value = globals[self.name]
        else:
            raise RuntimeError("Name '"+self.name+"' is not defined!")

        return self.resolveType(value, message, globals, locals)

class TCallback(DynamicType):

    def __init__(self, callback):

        self.callback = callback

    def evaluate(self, message, globals, locals):
        
        return self.callback()

class Token():

    def __init__(self, type, value, pos):

        self.type = type
        self.value = value
        self.pos = pos

    def __repr__(self):

        return "Token(%s, %s, [%i, %i])" % (self.type, self.value, self.pos[0], self.pos[1])

class DSLError(BaseException):

    pass

class ParserError(DSLError):

    pass

class TokenError(DSLError):

    def __init__(self, token, message):

        msg = "Error on token %s in line %i, column %i: %s" % (token.type, *token.pos, message)
        DSLError.__init__(self, msg)

class Namespace():

    def __init__(self, globals, locals, handles):

        self.globals = globals
        self.locals = locals
        self.handles = handles

class EventHandle():

    def __init__():

        pass

    def evaluate(self, message, globals, locals):

        pass

class Responder(EventHandle):

    def __init__(self, condition, response):

        self.condition = condition
        self.response = response

    def evaluate(self, message, globals, locals):
        
        if isinstance(self.condition, DynamicType):
            condition = self.condition.evaluate(message, globals, locals) #resolve dynamic types
        elif isinstance(self.condition, DSLType):
            condition = self.condition.value
        else:
            condition = self.condition

        if isinstance(self.response, DynamicType):
            response = self.response.evaluate(message, globals, locals) #resolve dynamic types
        elif isinstance(self.response, DSLType):
            response = self.response.value
        else:
            response = str(self.response)

        if condition:
            return response
        return ""

class Logger(EventHandle):

    def __init__(self, response, log, level=logging.DEBUG):

        self.response = response
        self.log = log
        self.level = level

    def evaluate(self, message, globals, locals):
        
        if isinstance(self.level, DynamicType):
            level = self.level.evaluate(message, globals, locals) #resolve dynamic types
        elif isinstance(self.level, DSLType):
            level = self.level.value
        else:
            level = int(self.level)

        if isinstance(self.response, DynamicType):
            response = self.response.evaluate(message, globals, locals) #resolve dynamic types
        elif isinstance(self.response, DSLType):
            response = self.response.value
        else:
            response = str(self.response)

        self.log.log(level, response)

        return ""

class AudioResponder(EventHandle):

    def __init__(self, condition, path, interpreter):

        self.condition = condition
        self.path = path
        self.interpreter = interpreter

    def evaluate(self, message, globals, locals):
        
        if self.condition.evaluate(message, globals, locals):
            p = self.path.evaluate(message, globals, locals)
            if not os.path.isfile(p):
                raise OSError("This file does not exist.")

            self.interpreter.playSound(p, message)

class ReactResponder(EventHandle):

    def __init__(self, condition, emoji, interpreter):

        self.condition = condition
        self.emoji = emoji
        self.interpreter = interpreter
        
    def evaluate(self, message, globals, locals):
        
        if self.condition.evaluate(message, globals, locals):
            e = self.emoji.evaluate(message, globals, locals)

            self.interpreter.addReaction(e, message)

class DSLParser():

    """
    Parser for the Chat Interaction Domain Specific Language (CIDSL).
    This is actually more of a tokenizer/lexer since it only operates
    on pure text input but whatever.
    Terminology is not important.
    """

    token_types = (
        ("comment", "//.+\\n"), #A comment spans accross the entire line until a newline occurs
        ("number", "[+-]?[0-9]+"),
        ("boolean", "True|False"),
        ("none", "None"),
        ("name", "[a-zA-Z_]?[a-zA-Z0-9_]+"),
        ("string", '".+?[^%]"'), #A string starts with " and ends with ", except if it is prepended with a % character
        ("actionSeparator", "->"),
        ("condSeparator", ", ?"),
        ("condAndStart", "\("),
        ("condAndEnd", "\)"),
        ("condOrStart", "\["),
        ("condOrEnd", "\]"),
        ("separator", " +"),
        ("inversion", "!"),
        ("substring", "#"),
        ("end", "[^%]?\\n|$"), #The end of a command is a newline, if it isn't prepended with a % character
        ("missmatch", ".")
        )

    token_string = '|'.join('(?P<%s>%s)' % pair for pair in token_types)
    token_pattern = re.compile(token_string)

    logger = logging.getLogger("CIDSL Parser")

    def __init__(self):

        pass

    def parse(self, code):

        """
        Parses the code and returns a sequence of tokens.
        """

        tokens = []

        self.logger.info("Parsing file...")

        line = 1
        start = 0

        for token in self.token_pattern.finditer(code):

            tType = token.lastgroup
            tValue = token.group(tType)
            
            if tType == "separator":
                continue
            elif tType == "comment":
                self.logger.debug("Skipping comment on line %i" % line)
                line += 1
                start = token.end()
                continue #discard comments
            elif tType == "missmatch":
                raise ParserError("Unexpected symbol on line %i, column %i: %s" % (line, token.start(), tValue))
            else:
                if tType == "end":
                    line += 1
                    start = token.end()
                to = Token(tType, tValue, [line, token.start() - start])
                self.logger.debug("Parsed "+str(to))
                yield to

        self.logger.info("Done.")

class DSLInterpreter():

    """
    Interpreter for the Chat Interaction Domain Specific Language (CIDSL).

    Also parses tokens into an AST and compiles responders.
    Because terminology isn't important.
    Again.
    """

    logger = logging.getLogger("CIDSL Interpreter")

    def __init__(self, client):

        self.client = client
        self.globals = {}
        self.namespaces = []
        self.audioManager = None

        self.setupDefaultNamespace()
        
    def playSound(self, sound, message):

        """
        Tries to play a sound in the server the message was sent from.
        If no sound backend is available, this method is a noop.
        """

        if not self.audioManager:
            return

        try:
            vc = message.guild.voice_client
            channel = vc.channel
        except AttributeError:
            return #This is easier than LBYL

        if not (vc and channel):
            return

        sound = FFMPEGSound(sound)
        self.audioManager.playSound(sound, channel, True)
        return True

    def addReaction(self, reaction, message):

        """
        Add a reaction to this message.
        """

        loop = self.client.loop
        try:
            loop.create_task(self.client.add_reaction(message, reaction))
        #Don't think this ever happens since the error should occur in the subroutine but whatever
        #Clean code is for scrubs
        except discord.DiscordException:
            return False
        return True

    def setupDefaultNamespace(self):

        """
        Defines a few useful globals.
        Includes the contents of the chat response files located at
        chat/responses
        """

        ls = (
            ("mentioned", mentioned),
            ("greet", greet),
            ("agree", agree),
            ("disagree", disagree),
            ("confused", confused),
            ("denied", denied),
            ("goodnight", goodnight)
            )
        for pair in ls:
            self.registerGlobalsCallback(pair[0], pair[1].getRandom)
        
        self.registerGlobalsCallback("bot_name", lambda: self.client.user.name)

    def _compileNumber(self, token):

        try:
            value = int(token.value)
        except:
            raise TokenError(token, "Number contains illegal character")
        return DSLType(value)

    def _compileString(self, token):

        return TString(token.value.strip('"'))

    def _compileBoolean(self, token):

        if not token.value in ("True", "False"):
            raise TokenError(token, "Boolean contains illegal character sequence %s" % token.value)
        return DSLType(token.value == "True")

    def _compileAndCondition(self, gen):

        expressions = []

        while True:
            expressions.append(self._compileExpression(gen))
            token = next(gen)
            if token.type == "condAndEnd":
                return TConditionAnd(*expressions)
            elif not token.type == "condSeparator":
                raise TokenError(token, "Unexpected symbol %s, expected ','" % token.value)

    def _compileOrCondition(self, gen):

        expressions = []

        while True:
            expressions.append(self._compileExpression(gen))
            token = next(gen)
            if token.type == "condOrEnd":
                return TConditionOr(*expressions)
            elif not token.type == "condSeparator":
                raise TokenError(token, "Unexpected symbol %s, expected ','" % token.value)

    def _compileInversion(self, gen):

        return TInversion(self._compileExpression(gen))

    def _compileSubstring(self, gen):

        try:
            string = next(gen)
        except StopIteration:
            raise DSLError("Unexpected EOF while parsing substring")

        if string.type != "string":
            raise TokenError(string, "Attempting to use substring operator on something that isn't a string.")

        return TSubstring(self._compileString(string))

    def _compileExpression(self, gen):

        #An "expression" in this context is anything that results in a value.
        #It may just be a literal, like a string or number, or a compound object,
        #like a condition or even nested conditions.
        
        token = next(gen) #let the error propagate, we need it to check for empty lines

        if token.type == "name":
            return TName(token.value)
        elif token.type == "number":
            return self._compileNumber(token)
        elif token.type == "string":
            return self._compileString(token)
        elif token.type == "condAndStart":
            return self._compileAndCondition(gen)
        elif token.type == "condOrStart":
            return self._compileOrCondition(gen)
        elif token.type == "inversion":
            return self._compileInversion(gen)
        elif token.type == "substring":
            return self._compileSubstring(gen)
        elif token.type == "actionSeparator":
            return TActionSeparator(token.value)
        elif token.type == "boolean":
            return self._compileBoolean(token)
        elif token.type == "none":
            return DSLType(None)
        elif token.type == "end":
            return None
        
        raise TokenError(token, "Unexpected symbol %s" % token.value)

    def _compileCommand(self, gen, locals, handles):

        """
        Compiles a command
        """

        commandName = self._compileExpression(gen)
        if commandName == None:
            return None #we're done here, terminate compilation
        elif not isinstance(commandName, TName):
            raise DSLError()

        args = []
        while True:
            try:
                arg = self._compileExpression(gen)
            except StopIteration:
                raise DSLError("Unexpected EOF while compiling command")
            if isinstance(arg, TActionSeparator):
                break
            elif arg == None:
                raise DSLError("Expected '->'")
            args.append(arg)

        action = []
        while True:
            try:
                a = self._compileExpression(gen)
            except StopIteration:
                raise DSLError("Unexpected EOF while compiling command")
            if a == None:
                break
            action.append(a)

        if commandName.name == "set":
            #set local variable
            if len(args) != 1:
                raise DSLError("Wrong amount of arguments for command 'set': Expected 1 but was %i" % len(args))
            if len(action) != 1:
                raise DSLError("Wrong amount of actions for command 'set': Expected 1 but was %i" % len(action))
            if not isinstance(args[0], TName):
                raise DSLError("Wrong argument type for command 'set': Must be %s but was %s" % (str(TName), str(args[0].__class__)))
            self.logger.debug("Executing 'set' command for local variable %s" % args[0].name)
            locals[args[0].name] = action[0]

        elif commandName.name == "load":
            #load lineStorage and add it to local dict
            if len(args) != 1:
                raise DSLError("Wrong amount of arguments for command 'load': Expected 1 but was %i" % len(args))
            if len(action) != 1:
                raise DSLError("Wrong amount of actions for command 'load': Expected 1 but was %i" % len(action))
            if not isinstance(args[0], TName):
                raise DSLError("Wrong argument type for command 'load': Must be %s but was %s" % (str(TName), str(args[0].__class__)))
            name = args[0].name
            #evaluate strings at loadtime (this isn't usually what we do but when dealing with files
            #certain precautions must be taken)
            path = str(action[0].evaluate("", self.globals, locals)) 
            self.logger.debug("Executing 'load' command for local variable %s: Loading line storage from file %s" % (name, path))
            ls = lineStorage(path) #load text file
            locals[name] = TCallback(ls.getRandom) #register lineStorage callback in local namespace

        elif commandName.name == "log":

            if len(args) > 1:
                raise DSLError("Command 'log' takes no arguments but %i were given" % len(args))
            if len(action) != 1:
                raise DSLError("Wrong amount of actions for command 'log': Expected 1 but was %i" % len(action))

            level = logging.DEBUG
            if args:
                level = args[0]

            self.logger.debug("Registering logger with level %s..." % str(level))
            handles.append(Logger(action[0], self.logger, level))

        elif commandName.name == "on":

            if len(args) != 1:
                raise DSLError("Wrong amount of arguments for command 'on': Expected 1 but was %i" % len(args))
            if len(action) < 1:
                raise DSLError("Not enough actions for command 'on': Expected at least 1 but was %i" % len(action))
            elif len(action) == 2:

                if isinstance(action[0], TName):

                    if action[0].name == "play":
                    
                        handle = AudioResponder(args[0], action[1], self)
                        self.logger.debug("Registering audio responder...")
                        handles.append(handle)
                        return True
                
                    elif action[0].name == "react":

                        handle = ReactResponder(args[0], action[1], self)
                        self.logger.debug("Registering reaction responder...")
                        handles.append(handle)
                        return True

                    else:
                        raise DSLError("Wrong value for first action, must be 'play' or 'react'.")

            elif len(action) > 2:
                raise DSLError("Too many actions for command on: Expected at most 2 but was %i" % len(action))

            #Path for normal text responses
            self.logger.debug("Registering responder...")
            handles.append(Responder(args[0], action[0]))

        return True #signal that we want more tokens

    def compile(self, gen):

        """
        Compiles the tokens into an AST, populates the namespace and sets up event handlers.
        """

        ns = Namespace(self.globals, {}, [])
        while True:
            try:
                self._compileCommand(gen, ns.locals, ns.handles)
            except StopIteration:
                break
        self.namespaces.append(ns)

    def run(self, message):

        """
        Run the interpreter on the given input message and dispatch output messages.
        Message should be of type discord.Message
        """

        results = []
        for i in self.namespaces:
            for handle in i.handles:
                result = handle.evaluate(message, i.globals, i.locals)
                if result:
                    results.append(result)

        if results:
            self.client.loop.create_task(message.channel.send("%s, %s" % (message.author.mention, "\n".join(results))))
            return True

        return False

    def setGlobal(self, name, value):

        """
        Set a global variable.
        This variable will be visible to and accessible by all loaded CIDSL scripts.
        """

        self.globals[name] = value

    def registerGlobalsCallback(self, name, callback):

        """
        Registers a callback as a global variable. Each time this variable is referenced,
        the callback will be called with no arguments and its return value is passed to
        the script as the value of the variable.
        """

        var = TCallback(callback)
        self.globals[name] = var

    def registerAudioEngine(self, audio_manager):

        """
        Registers an audio.AudioManager instance to playback audio
        """

        self.audioManager = audio_manager
