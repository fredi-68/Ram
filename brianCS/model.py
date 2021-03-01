#BrianCS Coversation Simulator
#
#Author: fredi_68
#
#This module includes the CS model class BrianModel as
#well as a number of other classes used by the implementation
#such as the Parser and the TokenTable.

#The BrianCS model is completely self contained. To create a
#model, create a new instance of BrianModel. To store the models
#state, use BrianModel.save() and BrianModel.load(), which will
#store and load states using zip archives.

#The BrianModel class has many parameters that may be adjusted
#to change model behavior and response. A number of these use
#enums for clarity, which are available in the brianCS.enums module.

import enum
from enum import Enum
import logging
import random
import multiprocessing
import os
import time
import re
import zipfile
import json
import io
import math

from .enums import *

PROCESS_COUNT = os.cpu_count()
if PROCESS_COUNT == None:
    PROCESS_COUNT = 0

ENABLE_MULTIPROCESSING = PROCESS_COUNT > 3 #we only use multiprocessing if we have 4 or more cores

class Message():

    """
    Message data class.
    """

    def __init__(self, data, timestamp):
        
        self.data = data
        self.timestamp = timestamp

class Token():

    def __init__(self, name, type, index, tag):

        self.name = name
        self.type = type
        self.index = index
        self.tag = tag

    def __eq__(self, other):

        if not isinstance(other, self.__class__):
            return False
        return (self.name == other.name and self.type == other.type and self.index == other.index and self.tag == other.tag)

class Result():

    """
    Result data class.
    """

    def __init__(self, result, probability):

        self.result = result
        self.probability = probability

class TokenTable():

    """
    Stores tokens and their respective internal representation.
    """

    logger = logging.getLogger("TokenTable")

    def __init__(self):

        self.mapping = {}

    def addToken(self, name, type=TokenTypes.WORD, tag=Tags.NOUN):

        ind = len(self.mapping)
        token = Token(name, type, ind, tag)
        self.mapping[name] = token
        return token

    def getTokenByName(self, name):

        return self.mapping[name]

    def getTokenByID(self, ID):

        return list(self.mapping.values())[ID]

    def deleteToken(self, ID):

        t = self.getTokenByID(ID)
        del self.mapping[t.name]

    def hasToken(self, name):

        return name in self.mapping

    def getRandom(self):

        return random.choice(list(self.mapping.values()))

    def load(self, f):

        self.logger.debug("Clearing table...")
        self.mapping.clear()
        self.logger.info("Loading...")

        d = json.load(f)
        for name, token in d.items():
            self.mapping[name] = Token(name, TokenTypes(token["type"]), token["ind"], Tags(token["tag"]))

    def save(self):

        self.logger.info("Saving...")

        d = {}
        for name, token in self.mapping.items():
            d[name] = {
                "type": token.type.value,
                "ind": token.index,
                "tag": token.tag.value
                }

        return json.dumps(d)

class Node():

    """
    This class represents a Node in a HMM graph.
    Each node tracks it's associated value as well as the values of the preceeding nodes.
    """

    def __init__(self, *args, index=-1):

        self.args = tuple(args)
        self.value = args[-1]
        self.previous = args[:-1]
        self.order = len(self.args)
        self.index = index
        
    def __str__(self):

        return "<Node value=" + str(self.args[-1]) + ((", previous=%s" % str(self.args[:-1])) if len(self.args) > 1 else "") + ">"

    def __eq__(self, value):
        
        if not isinstance(value, Node):
            return False
        return self.index == value.index

    def __hash__(self):
        
        return hash(self.index)

class Edge():

    """
    This class represents a connection between two nodes in a HMM graph.
    Each edge stores a reference to it's source and target node, as well as
    their respective indices. It also stores the weighting for this particular
    connection.
    """

    def __init__(self, fromInd, toInd, fromN, toN, weight=1.0):

        assert isinstance(fromInd, int)
        assert isinstance(toInd, int)

        self.fromInd = fromInd
        self.toInd = toInd
        self.fromNode = fromN
        self.toNode = toN
        self.weight = float(weight)

class MModel():

    """
    Implementation of a n-th order Hidden Markov Model (HMM).
    """

    logger = logging.getLogger("HMM")

    def __init__(self, order, starting_weight=100, weight_increase=10):

        self.order = order #TODO: Add the option to create a graph with infinite memory
        self.starting_weight = starting_weight
        self.weight_increase = weight_increase
        self.nodes = {0: None}
        self.edges = []
        self._nextIndex = 0

    def addEdge(self, fromInd, toInd, weight=1):

        """
        Add a new edge connecting two nodes.
        """

        edge = Edge(fromInd, toInd, self.nodes[fromInd], self.nodes[toInd], weight)
        self.edges.append(edge)
        return edge

    def deleteEdge(self, fromInd, toInd):

        """
        Delete the edge connecting two nodes
        """

        edge = self.findEdge(fromInd, toInd)
        self.edges.remove(edge)

    def findEdge(self, fromInd, toInd):

        """
        Find the edge connecting two nodes.
        """

        assert isinstance(fromInd, int)
        assert isinstance(toInd, int)

        for edge in self.edges:
            if edge.fromInd == fromInd and edge.toInd == toInd:
                return edge
        raise KeyError("No edge from %i to %i exists in this graph." % (fromInd, toInd))

    def parseToken(self, value, previous=None):

        """
        Reads a token in a sequence.
        value is the value of the token, previous a reference to the parent node.
        This method returns a reference to the node representing this token.
        """

        if previous:
            l = list(previous.args[1:])
            l.append(value)
        else:
            l = [value]
        try:
            node = self.findNodeForArgs(l)
            #if this call succeeds, this means we already have a node with this exact configuration.
            #If we encounter this case, we increase the weight of the edge connecting this node to its
            #parent, then return the existing node.
            nodeInd = self.getIndex(node)
            preInd = self.getIndex(previous)
            try:
                edge = self.findEdge(preInd, nodeInd)
            except KeyError:
                edge = self.addEdge(preInd, nodeInd, 0)
            edge.weight += self.weight_increase
            return node
        except ValueError:
            #print("Adding new node for value %s" % str(value))
            return self.addNode(value, previous, self.starting_weight)

    def getNextIndex(self):

        self._nextIndex += 1
        return self._nextIndex

    def getIndex(self, node):

        if node is None:
            return 0
        return node.index

    def addNode(self, value, previous=None, weight=1):

        """
        Adds a new node to the graph.
        """
        
        prevArgs = previous.args[-(self.order-1):] if previous else []
        node = Node(*prevArgs, value, index=self.getNextIndex())
        prevInd = self.getIndex(previous)
        newInd = self.getIndex(node)
        self.nodes[newInd] = (node)
        self.addEdge(prevInd, newInd, weight)
        return node

    def addStop(self, node, weight=1):

        """
        Add a terminator to this node.
        A terminator signals the sequence generator that the sequence has been completed.
        """

        prevInd = node.index
        self.addEdge(prevInd, 0, weight)

    def findNodeForArgs(self, args):

        """
        Return the node described by the provided arguments.
        If less than order arguments are provided, an arbitrary node will be returned that
        matches the partial argument list.
        Arguments are always matched in order.
        """

        args = tuple(args)
        if not args:
            return None
        if len(args) > self.order:
            raise ValueError("Invalid argument count for model of order %i: Was %i." % (self.order, len(args)))
        for i in self.nodes.values():
            if i == None:
                continue
            if i.args[-len(args):] == args:
                return i
        raise ValueError("Could not find a node that satisfies the provided conditions: %s" % str(args))

    def getNext(self, node=None):

        """
        Return the next token in a sequence of tokens.
        The sequence is randomly generated. Each token is guaranteed to be part of the set of
        fed tokens. Distribution is done according to probability of the token appearing in
        the given context.
        This method is non deterministic.
        """

        weights = []
        targets = []
        for edge in self.edges:
            if edge.fromNode == node:
                targets.append(edge.toInd)
                weights.append(max(edge.weight, 1))
        choice = random.choices(targets, weights, k=1)[0]
        return self.nodes[choice]

    def getSequence(self, startAt=None):

        """
        Return a sequence of tokens, randomly distributed according to fed token sequence probabilities.
        This method is non deterministic.
        If startAt is given, it should be a token that is part of this graph. It will be used as a starting
        point for the sequence generator.
        """

        lastNode = self.getNext(startAt)
        seq = []
        while lastNode:
            seq.append(lastNode.value)
            lastNode = self.getNext(lastNode)
        return seq

    def feed(self, seq):

        """
        Feed a sequence of tokens into the model.
        This method will analyze the input sequence, build the evaluation graph and adjust edge weights accordingly.
        """

        lastNode = None
        for i in seq:
            lastNode = self.parseToken(i, lastNode)
        self.addStop(lastNode, self.starting_weight)

    def _sanitize(self, nodes):

        dirty_nodes = []

        #Step 1: Walk the nodes, checking for edges that have this node as a source
        for node in nodes:
            if node is None:
                continue #Ignore termination token
            for edge in self.edges:
                if edge.fromNode == node:
                    break
            else:
                #Step 2: This node does not connect to any other node.
                #This means the path has been broken, remove all source edges.
                self.logger.debug("Node %s has no target, removing all source edges." % str(node))
                for edge in self.edges[:]:
                    if edge.toNode == node:
                        self.edges.remove(edge)
                        dirty_nodes.append(edge.fromNode)

        #Step 3: Return list of nodes that were affected
        #so they can be checked
        return dirty_nodes

    def sanitize(self, nodes=None):

        """
        Walks the graph and cleans up any loose paths that have become disconnected.
        If nodes is given, it should be a list of Node instances, otherwise self.nodes
        will be used. This argument may be used to limit the amount of nodes visited,
        which can significantly speed up the algorithm.
        """

        if nodes is None:
            nodes = self.nodes.values()

        dirty_nodes = set(nodes)

        r = 1
        while nodes:
            self.logger.debug("Looking for disconnected paths (round %i)..." % r)
            nodes = self._sanitize(nodes)
            dirty_nodes.update(nodes)
            r += 1

        self.logger.debug("Graph sanitized.")
        return dirty_nodes

    def dropout(self, policy=Dropout.RANDOM_WEIGHTED, curve=DropoutCurve.DECREMENT, factor=0.5, threshold=0):

        """
        Perform token dropout on the whole model using the specified policy and weighting curve.
        The curve is applied first, adjusting the weights of the entire model.
        After this step, dropout is performed according to the chosen policy.

        After edges have been cleaned up, the entire graph is checked for loose paths which will be
        deleted. This process can take a long time.

        How factor and threshold are applied depends on the chosen dropout algorithm.
        """

        #Step 1: Accumulate and adjust weights
        edge_weights = []
        for edge in self.edges:
            if curve == DropoutCurve.DECREMENT:
                edge.weight -= 1
            elif curve == DropoutCurve.HALF:
                edge.weight /= 2
            elif curve == DropoutCurve.LOG2:
                if edge.weight > 1:
                    edge.weight = math.log2(edge.weight)
                else:
                    edge.weight = 0.0
            elif curve == DropoutCurve.LOG10:
                if edge.weight > 1:
                    edge.weight = math.log10(edge.weight)
                else:
                    edge.weight = 0.0

            elif curve == DropoutCurve.SQUARE_ROOT:
                edge.weight = float(edge.weight ** 0.5)

            if edge.weight < threshold:
                edge_weights.append(edge)

        #Step 2: Drop edges.
        #The following algorithms are currently available:
        #
        #Random - Drop random edges below weight threshold. Factor specifies how likely an edge is to be dropped.
        #Random weighted - Drop random edges below weight threshold after inverting their weights to seed the randomizer.
        #   The final weights are multiplied by factor.
        #Least used - Drop edges with the lowest weight. factor specifies the amount of edges to drop.
        #All - All edges below threshold are dropped. factor is ignored.
        #None - No edges will be dropped.

        if edge_weights:
            self.logger.debug("There are %i edge(s) below the weight threshold. Applying dropout policy..." % len(edge_weights))

        deleted = set()

        if policy == Dropout.NONE:
            pass

        elif policy == Dropout.ALL:
            for edge in edge_weights:
                deleted.add(edge.fromNode)
                deleted.add(edge.toNode)
                self.edges.remove(edge)

        elif policy == Dropout.LEAST_USED:
            edges = edge_weights[:]

            def sort(x):
                return x.weight
            edges.sort(key=sort)
            amount = int(len(edges)*factor)
            for edge in edges[:amount]:
                deleted.add(edge.fromNode)
                deleted.add(edge.toNode)
                self.edges.remove(edge)

        elif policy == Dropout.RANDOM:
            for edge in edge_weights:
                if random.random() < factor:
                    deleted.add(edge.fromNode)
                    deleted.add(edge.toNode)
                    self.edges.remove(edge)

        elif policy == Dropout.RANDOM_WEIGHTED:
            edges = edge_weights[:]
            amount = int(len(edges)*factor)
            selection = []
            for i in range(amount):
                f = lambda x: -x.weight*factor
                weights = list(map(f, edges))
                m = min(weights)
                if m < 1:
                    pad = 1 - m
                    for j in range(len(weights)):
                        weights[j] = weights[j] + pad
                s = random.choices(edges, weights, k=1)[0]
                selection.append(s)
                edges.remove(s)
            for edge in selection:
                deleted.add(edge.fromNode)
                deleted.add(edge.toNode)
                self.edges.remove(edge)

        #save processing time by exiting early if we didn't drop any edges
        if not deleted:
            return
        deleted = self.sanitize(deleted)

        #Step 3: Drop nodes.
        #We only need to check nodes that had edges dropped, which is why we are keeping track of them
        #in a set.
        #However, it is not enough to check for disconnected nodes, we have to check for disconnected Paths too.
        #in essence this means that we have to walk the nodes that were changed and check if they have any alternative
        #paths. If not, we drop the remaining edges as well and repeat the cycle. This is to prevent the graph from
        #running into a dead end during execution.
        #This is what the sanitize method does. It returns the total set of nodes that were affected by the dropout
        #process. Any nodes that don't have edges connecting them can be safely removed.
        #An alternative would be to check if a node has an alternative path before removing an edge.
        #Experimentation is needed to find the best approachd/solution here.

        for node in deleted:
            if node == None:
                continue #Don't drop the terminating node
            for edge in self.edges:
                if node in (edge.fromNode, edge.toNode):
                    break
            else:
                #No edges connected to this node, drop it
                self.logger.debug("Dropping node %s: Node is isolated." % str(node))
                del self.nodes[node.index]

    def save(self):

        self.logger.info("Saving HMM graph...")
        nodes = {}
        for node in self.nodes.values():
            if node == None:
                continue
            nodes[str(node.index)] = {"v": node.value, "p": node.previous}

        edges = []
        for edge in self.edges:
            e = {"s": edge.fromInd, "d": edge.toInd, "w": edge.weight}
            edges.append(e)

        d = {"nodes": nodes, "edges": edges}

        return json.dumps(d)

    def load(self, f):

        self.logger.debug("Clearing node store...")
        self.nodes.clear()
        self.logger.debug("Clearing edge store...")
        self.edges.clear()

        self.logger.info("Loading HMM graph...")
        d = json.load(f)

        self.nodes = {0: None}
        maxIndex = 0
        for ind, node in d["nodes"].items():
            i = int(ind)
            self.nodes[i] = Node(*node["p"], node["v"], index=i)
            maxIndex = max(maxIndex, i)

        self._nextIndex = maxIndex

        for edge in d["edges"]:
            fromInd = edge["s"]
            toInd = edge["d"]
            weight = edge["w"]
            self.edges.append(Edge(fromInd, toInd, self.nodes[fromInd], self.nodes[toInd], weight))

class PoSTagger():

    """
    BrianCS Part of Speech (PoS) tagger.

    Takes a sequence of tokens and tags them with information about part of speech.
    Used as supplemental input for the main model.
    """

    logger = logging.getLogger("BrianCS Tagger")

    def __init__(self):

        pass

class Parser():

    """
    Parser for the BrianCS model.
    Parses a string into a sequence of tokens and translates them into
    a sequence of integers. Tokens are stored internally using a TokenTable.
    This class provides an interface for translating between numerical token IDs
    and plain text.
    """

    logger = logging.getLogger("BrianCS Parser")

    PATTERNS = (
        ("LINK", r"""(?:[A-Za-z]+?://)?[0-9A-Za-z]+\.[0-9A-Za-z\-]+\.[A-Za-z]+(?:/.*)?"""),
        ("WORD", r"""[0-9A-Za-z]+"""),
        ("SEPARATOR", r"""[.,;: '"\-\(\)\[\]\{\}]"""),
        ("MISMATCH", r""".""")
        )

    PATTERN = re.compile('|'.join('(?P<%s>%s)' % pair for pair in PATTERNS))

    def __init__(self, table):

        self.table = table
        self.tagger = PoSTagger()

    def tokenize(self, msg):

        """
        Split a text message into a sequence of tokens.
        """

        tokens = []
        for token in self.PATTERN.finditer(msg):
            type = token.lastgroup
            value = token.group(type)
            tokens.append((value, type))
        return tokens

    def parse(self, msg):

        """
        Tokenizes and translates a text message into a sequence of tokens.
        """

        tokens = self.tokenize(msg)

        seq = []
        #TODO: run message through tagger to obtain PoS information
        for token, type in tokens:
            if self.table.hasToken(token):
                seq.append(self.table.getTokenByName(token))
                continue
            eType = TokenTypes.WORD
            if type == "SEPARATOR":
                eType = TokenTypes.SEPARATOR
            elif type == "LINK":
                eType = TokenTypes.LINK
            seq.append(self.table.addToken(token, eType, Tags.NOUN))

        return seq

    def build(self, seq):

        """
        Translate a sequence of numerical IDs into plaintext through token table lookup.
        """

        tokens = []
        for ID in seq:
            tokens.append(self.table.getTokenByID(ID).name)

        return "".join(tokens)

class BrianModel():

    """
    The BrianCS model.

    This class wraps a HHMM used for text prediction and context handling.
    Supports multiple parallel conversations.
    """

    logger = logging.getLogger("BrianCS Model")

    def __init__(self, timeout=Timeout.LOGARITHMIC, dropout=Dropout.LEAST_USED, dropout_curve=DropoutCurve.DECREMENT,
                 message_buffer=2, prediction_time=500, max_predictions=300,
                 context_bias=0.5, dropout_chance=0.0002, dropout_factor=0.001):

        """
        Create a new model and initialize it.

        timeout specifies the timeout policy used by the context awareness algorithm
        dropout specifies the dropout policy used for reducing model size
        message_buffer specifies the size of the message backlog buffer used to provide context to messages
        prediction_time specifies the time the model should spend generating candidate replies before evaluating
        max_predictions specifies the maximum amount of candidate replies the model should generate before evaluating
        context_bias is the percentage of the votes on reply candidates that is cast by the context awareness algorithm
        dropout_chance specifies the probability of dropout being applied on a state.
        """

        self.timeout = timeout
        self.dropout = dropout
        self.dropout_curve = dropout_curve
        self.message_buffer = message_buffer
        self.prediction_time = prediction_time
        self.max_predictions = max_predictions
        self.context_bias = context_bias
        self.dropout_chance = dropout_chance
        self.dropout_factor = dropout_factor

        self.conversations = {}

        self.tokenTable = TokenTable()
        self.blacklist = []

        self.parser = Parser(self.tokenTable)

        self.modelOrder = 6
        self.genForward = MModel(self.modelOrder)
        self.genBackward = MModel(self.modelOrder)

    def train(self, data):

        """
        Train the model on the given data.
        Data should be a list of strings, each denoting its own message.
        """

        for i in data:
            self.observe(i)

    def perform_dropout(self, amount):

        """
        Reduce the size of the model by dropping states according to the set dropout policy.
        This method can be quite computationally expensive.
        """

        self.logger.debug("Performing edge dropout...")
        self.genForward.dropout(self.dropout, self.dropout_curve, amount, self.dropout_chance)
        self.genBackward.dropout(self.dropout, self.dropout_curve, amount, self.dropout_chance)

    def _evaluate_current(self, candidates, input):

        """
        Evaluates a list of candidates and rates them according to relevance
        to the current input sequence.
        This method returns a list of floats of the same length as the input
        sequence representing the rating for each response candidate.
        """

        return [1] * len(candidates)

    def _evaluate_conversation(self, candidates, conversation=None):

        """
        Evaluates a list of candidates and rates them according to relevance
        to the current conversation.
        This method returns a list of floats of the same length as the input
        sequence representing the rating for each response candidate.
        """

        return [1] * len(candidates)

    def updateConversation(self, tokens, conversation=None, timestamp=None):

        """
        Update the conversation using the specified token list.
        If conversation is None, this method is a no op.
        If timestamp is not provided or None, the current time as returned
        by time.time() is used instead.
        """

        if conversation is None:
            return

        if timestamp is None:
            timestamp = time.time()

        msg = Message(tokens, timestamp)
        if not conversation in self.conversations:
            self.conversations[conversation] = [msg]
        else:
            c = self.conversations[conversation]
            if len(c) >= self.message_buffer:
                c.pop(0)
            c.append(msg)

    def observe(self, message, conversation=None):

        """
        Observe a message typed by another user.
        This method will read the input message and apply its contents to the model.
        If conversation is not None, it should be a keyword identifying the conversation this message belongs to.
        """

        tokens = self.parser.parse(message)

        self.updateConversation(tokens, conversation)

        numTokens = list(map(lambda x: x.index, tokens))
        self.genForward.feed(numTokens)
        numTokens.reverse()
        self.genBackward.feed(numTokens)

        self.perform_dropout(self.dropout_factor)

    def generate(self, token):

        """
        Generate a candidate reply.
        """

        #generate reply sequence
        tail = self.genForward.getSequence(self.genForward.findNodeForArgs([token.index]))
        args = tail[:self.modelOrder-1]
        head = self.genBackward.getSequence(self.genBackward.findNodeForArgs([*args[::-1], token.index]))
        head.reverse() #make sure to reverse since the returned sequence is generated backwards
        return head + [token.index] + tail

    def filter(self, tokens):

        """
        Pre-filter generator input.
        Removes tokens based on part of speech tag and a word based blacklist.
        """

        res = []
        for i in tokens:
            if not i.type in (TokenTypes.WORD, TokenTypes.LINK):
                continue
            if i.tag in (Tags.PRONOUN,):
                continue
            if i.name in self.blacklist:
                continue
            res.append(i)

        return res

    def respond(self, message, conversation=None):

        """
        Respond to a message typed by another user.
        This method will read the input and generate reply canditates. Candidates are automatically evaluated and
        the one deemed most suitable by the model will be returned as a string.
        After generating, the model will be automatically updated using the input as training data. It is thus
        unnecessary to subsequently train the model on the same input after calling this method.

        If conversation is not None, it should be a keyword identifying the conversation this message belongs to.
        """

        #Do tokenizing, parsing and filtering
        tokens = self.parser.parse(message)
        numTokens = list(map(lambda x: x.index, tokens))
        tokens = self.filter(tokens)
        if not tokens:
            tokens.append(self.tokenTable.getRandom())

        #Generate replies
        startTime = time.time()
        results = []
        self.logger.debug("Generating responses...")
        while time.time() - startTime < self.prediction_time/1000:
            token = random.choice(tokens)
            try:
                results.append(self.generate(token))
            except ValueError as e:
                self.logger.debug("Removing token %s from seed: %s" % (token.name, str(e)))
                tokens.remove(token)
                if not tokens:
                    tokens.append(self.tokenTable.getRandom())
                continue
            if len(results) >= self.max_predictions:
                break

        #TODO: Implement evaluation stage
        self.logger.debug("Evaluating responses...")
        current_w = self._evaluate_current(results, tokens)
        conv_w = self._evaluate_conversation(results, conversation)
        final_w = []
        for i in range(len(results)):
            v = conv_w[i] * self.context_bias + current_w[i] * (1 - self.context_bias)
            final_w.append(v)

        c = random.choices(results, weights=final_w, k=1)[0] #choose final candidate based on evaluation
        result = self.parser.build(c)

        #Train models
        self.genForward.feed(numTokens)
        numTokens.reverse()
        self.genBackward.feed(numTokens)

        self.perform_dropout(self.dropout_factor)

        return result

    def loadBlacklist(self, f):

        """
        Load a blacklist from a file.

        f can be a path or a file like object (supporting the readline protocol)

        Blacklist files should be normal textfiles with one entry per line.
        Lines starting with "//" will be ignored.
        Input for the prediction engine will be filtered according to this list.
        Any tokens in the input stream that match the list will be silently dropped.
        This does NOT affect the sequences used for training the model, even if
        training occurs after prediction on the same sequence of input tokens.
        """

        self.blacklist = []

        CLOSE = False
        if not hasattr(f, "readline"):
            f = open(f, "r")
            CLOSE = True

        while True:
            l = f.readline()
            if not l:
                break
            elif l.startswith("//"):
                continue
            self.blacklist.append(l.strip().lower())

        if CLOSE:
            f.close()

        self.logger.info("Loaded blacklist from file '%s'" % str(f))

    def saveBlacklist(self):

        """
        Dumps the blacklist to a string and returns it.
        """

        return "\n".join(self.blacklist)

    def load(self, path):

        """
        Load a model from a file.
        """

        self.logger.info("Loading model configuration...")

        try:
            f = zipfile.ZipFile(path)
        except OSError as e:
            self.logger.error("Loading model failed: %s" % str(e))
            return
        d = json.load(f.open("model.json"))
        self.timeout = Timeout(d["timeout"])
        self.dropout = Dropout(d["dropout"])
        self.message_buffer = d["message_buffer"]
        self.prediction_time = d["prediction_time"]
        self.max_predictions = d["max_predictions"]
        self.context_bias = d["context_bias"]
        self.dropout_chance = d["dropout_chance"]
        self.modelOrder = d.get("model_order", 4)
        self.dropout_factor = d.get("dropout_factor", self.dropout_factor)
        self.dropout_curve = DropoutCurve(d.get("dropout_curve", self.dropout_curve.value))

        self.tokenTable.load(f.open("table.dat"))

        self.genForward.order = self.modelOrder
        self.genBackward.order = self.modelOrder
        self.genForward.load(f.open("model1.dat"))
        self.genBackward.load(f.open("model2.dat"))

        try:
            bl = f.open("blacklist.txt")
            wrap = io.TextIOWrapper(bl)
            self.loadBlacklist(wrap)
        except KeyError:
            pass

        self.logger.info("Loading complete!")

    def save(self, path):

        """
        Save this model to a file.
        """

        f = zipfile.ZipFile(path, "w")

        #Settings (model.json)
        d = {
            "timeout": self.timeout.value,
            "dropout": self.dropout.value,
            "message_buffer": self.message_buffer,
            "prediction_time": self.prediction_time,
            "max_predictions": self.max_predictions,
            "context_bias": self.context_bias,
            "dropout_chance": self.dropout_chance,
            "model_order": self.modelOrder,
            "dropout_curve": self.dropout_curve.value,
            "dropout_factor": self.dropout_factor
            }
        self.logger.info("Saving model configuration...")
        f.writestr("model.json", json.dumps(d, indent=4))

        #Token table
        f.writestr("table.dat", self.tokenTable.save())

        #Models
        f.writestr("model1.dat", self.genForward.save())
        f.writestr("model2.dat", self.genBackward.save())

        #Blacklist
        f.writestr("blacklist.txt", self.saveBlacklist())

        f.close()
        self.logger.info("Backup complete!")
