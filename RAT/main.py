#RAT host for ProtOS Discord Bot
#author: fredi_68

import asyncio
import logging
import logging.config
import logging.handlers
import hashlib
import socket
import ssl
import struct
import sys
import subprocess
import os
import shutil
import traceback
import time
import datetime
import functools
import zlib
import argparse
import json
import pathlib

#may not need this if TimedRotatingFileHandler does its job correctly

##Clean up any old logs
#try:
#    for f in os.listdir("logs"):
#        try:
#            os.remove(f)
#        except OSError: #we don't want to abort the whole process if one file operation fails, thus we need two safety nets
#            pass
#except OSError:
#    pass #log folder may not exist

LOGGING_DICT = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "fileFormatter": {
            "format": "[%(asctime)s][%(name)s][%(levelname)s]: %(message)s",
            "datefmt": None
            },
        "terminalFormatter": {
            "format": "[%(asctime)s][%(name)s][%(levelname)s]: %(message)s",
            "datefmt": None
            }
        },
    "filters": {
        },
    "handlers": {
        "logFileHandler": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "level": "DEBUG",
            "filename": "logs/rat_access_log",
            "when": "midnight",
            "backupCount": 14,
            "formatter": "fileFormatter"
            },
        "terminalLogging": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "terminalFormatter"
            }
        },
    "loggers": {
        },
    "root": {
        "handlers": ["logFileHandler", "terminalLogging"],
        "level": "DEBUG"
        }
    }

from network import *
from perm import DatabaseHandle, User

VERSION = [2, 2, 3]
S_VERSION = "v%i.%i.%i" % tuple(VERSION)
S_TITLE_VERSION = "ProtOS Discord Bot RAT Host %s" % S_VERSION

APP_RC_PORT = 50010
RAT_PORT = 50050
RAT_HOST = "0.0.0.0"

UPDATE_PATH = "../"
PATCH_PATH = "./Patch/"
APP_PATH = "../ProtOS_Bot.py"

HASHING_BUFFER_SIZE = 4096

#SSL authentication certificate information
ENABLE_SSL=True
CERT_FILE="Security/server_certificate.pem"
CERT_KEY="Security/server_certificate.key"
CERT_PASSW=""

if sys.path[0]: #set cwd in case that the script was started from a different directory than the bot root
    try:
        os.chdir(sys.path[0]) #this needs to be done before any app level modules are imported to prevent ImportErrors
    except NotADirectoryError:
        pass #This can happen if we are running the application in an environment that is not a filesystem (for example, a frozen binary distribution)

def checkCredentials(db, username, password):

    """
    Check, if the given password matches the specified user
    """

    #Read stored key
    user = db.getUser(username)
    return user.checkKey(password)

def processFileList(filelist):

    """
    Process a filelist and check for changed or absent files to be patched
    """

    patchlist = []
    for entry in filelist:
        path = (pathlib.PureWindowsPath(UPDATE_PATH) / entry[0]).as_posix()
        if not os.path.isfile(path): #file doesn't exist, mark it to be patched
            patchlist.append(entry[0])
            continue
        try:
            f = open(path, "rb")
        except:
            continue

        h = hashlib.md5()
        while True:
            data = f.read(HASHING_BUFFER_SIZE)
            if not data:
                break
            h.update(data)
        f.close()
        if not h.digest() == entry[1]: #hashes don't match, mark it to be patched
            patchlist.append(entry[0])
    return patchlist

def createFile(path):

    """
    Creates the file at path and all directories needed to contain it
    """

    path = (pathlib.PureWindowsPath(PATCH_PATH) / path).as_posix() #our file path
    #now make sure all directories exist befor attempting to create the file
    os.makedirs(os.path.split(path)[0], exist_ok=True)
    f = open(path, "wb") #open in binary write mode so the updater can actually write our patch data
    return f

def getInterpreterCommand():

    logger = logging.getLogger("config")
    configPath = "config/rat.json"
    if not os.path.isfile(configPath):
        f = open(configPath, "w")
        f.close()
        logger.warn("config/rat.json was not found; defaulting to interpreter invocation command 'python'.")
        return "python"
    with open(configPath) as f:
        d = json.load(f)
        try:
            return d["interpreter"]["command"]
        except KeyError:
            logger.warn("The interpreter invocation command was not specified, please check your config/rat.json configuration file; defaulting to 'python'.")
            return "python"

class Client():

    """
    Client handle.
    This class represents a single client connection to the host.
    It handles all communication between the client and the host
    and is also responsible for patch downloading.
    """

    def __init__(self, host, reader, writer):

        self._logger = logging.getLogger("RC client handle")

        self.host = host
        self.reader = reader
        self.writer = writer

        self.is_authenticated = False
        self.user = None

        self._logger.info("Client handle created. Now serving interactive command requests")
        self.host.loop.create_task(self.mainLoop()) #start processing client requests

    async def sendError(self, errormsg=b""):

        """
        Send an error message to the client.
        """

        ret = NetworkPacket()
        ret.setOpCode(ret.OP_ERROR)
        if errormsg:
            ret.addField("description", errormsg)
        self._logger.error("Communication error: " + errormsg.decode())
        await self.sendPacket(ret)

    async def handleLogin(self, packet):

        """
        Login handle
        This method will automatically authenticate the client
        """

        #The client sends his authentication data with the login packet.
        #There are two fields guaranteed: username, which is the username we check against, and credentials, which is the hashed version of the password
        #Next we hash the password again together with the username to obfuscate the original password hash
        #We check the credentials against the saved user password and if they match we authenticate the client

        self._logger.info("Client logging in...")
        try:
            username = packet.getField("username")
            credentials = packet.getField("credentials")
        except:
            await self.sendError(b"illegal auth packet")
            return

        #Good, now we have the username and credentials
        #Next we compute the hash to check against
        h = hashlib.sha512()
        h.update(credentials)
        h.update(username)
        fh = h.digest() #Our new credentials

        if not checkCredentials(self.host.userdb, username.decode(), fh):
            await self.sendError(b"wrong login credentials")
            return

        self.user = username.decode()

        self._logger.info("Client logged in as " + username.decode())

        self.is_authenticated = True
        ret = NetworkPacket()
        ret.setOpCode(ret.OP_OK)
        await self.sendPacket(ret)
        return

    async def handleLogout(self, packet):

        """
        Logout handle.
        This method automatically logs the client out and disconnects
        """

        self._logger.debug("Client logging out...")
        self.is_authenticated = False #unnecessary but good practice
        ret = NetworkPacket()
        ret.setOpCode(ret.OP_OK)
        await self.sendPacket(ret) #there is a good chance that this will fail if the client has already closed connections
        self._logger.info("Client logged out.")
        self.disconnect()

    async def handleCommand(self, packet):

        """
        Command handle.
        This method will handle all application specific commands.
        Commands are checked for integrity and then passed to the host.
        The result will be sent back to the client after execution has completed.
        """

        #check permissions
        user = self.host.userdb.getUser(self.user)
        if not user.permissions["runCommands"]:
            await self.sendError(b"insufficient permission")
            return

        try:
            cmd = packet.getField("cmd")
        except:
            await self.sendError(b"illegal cmd packet")
            return

        try:
            res = await self.host.runCommand(cmd)
        except:
            await self.sendError(b"rpc failed")
            return
        ret = NetworkPacket()
        if not res:
            ret.setOpCode(ret.OP_NOOP)
            await self.sendPacket(ret)
        else:
            ret.setOpCode(ret.OP_OK)
            ret.addField("response", res)
            await self.sendPacket(ret)

    async def handleRATCommand(self, packet):

        """
        RAT command handle.
        Executes a command on the RAT host process and sends th result back to the client.
        """

        #Check permissions
        user = self.host.userdb.getUser(self.user)
        if not user.permissions["runRATCommands"]:
            await self.sendError(b"insufficient permission")
            return

        try:
            cmd = packet.getField("cmd")
        except:
            await self.sendError(b"illegal ratcmd packet")
            return

        self._logger.info("Client requested RAT internal command execution for " + cmd.decode())

        try:
            res = await self.host.runRATCommand(cmd, self.user)
        except:
            await self.sendError(b"rpc failed")
            return
        if isinstance(res, bytes) or res == None: #if the command handler returns a simple status message or nothing at all we will handle basic response functionality
            ret = NetworkPacket()
            if not res:
                ret.setOpCode(ret.OP_NOOP)
                await self.sendPacket(ret)
            else:
                ret.setOpCode(ret.OP_OK)
                ret.addField("response",res)
                await self.sendPacket(ret)
        elif isinstance(res, NetworkPacket): #if the command handler chooses to handle packet creation itself we pass it on without altering it
            await self.sendPacket(res)
        else:
            await self.sendError(b"rpc failed, illegal response type")

    async def _downloadFile(self, path, compress=False):

        """
        Download helper.
        Dowloads a file from the client and stores it
        """

        f = createFile(path)

        if compress:
            compObj = zlib.decompressobj()

        while True:
            packet = await self.receivePacket()
            if packet.opcode == packet.OP_UPDATE_TRANSFER:

                #confirm we are using gzip compression
                if not "compression" in packet.getFields() or packet.getField("compression") != b"gzip":
                    compress = False

                data = packet.getField("data")
                if compress:
                    data = compObj.decompress(data)

                f.write(data)
                ret = NetworkPacket()
                ret.setOpCode(ret.OP_CONT)
                await self.sendPacket(ret)

            elif packet.opcode == packet.OP_NOOP:

                #If we are compressing, make sure we don't loose any data
                if compress:
                    data = compObj.flush()
                    f.write(data)

                break

            else:
                raise RuntimeError("Illegal request")

        f.close()
        return True

    async def handleUpdate(self, packet):

        """
        Update handle.
        This method handles the complete update process up to applying the patch.
        After that it will automatically invoke the host updater.
        """

        #Check permissions
        user = self.host.userdb.getUser(self.user)
        if not user.permissions["update"]:
            await self.sendError(b"insufficient permission")
            return

        if self.host.updating: #make sure that only one client is uploading patch data at once
            await self.sendError(b"update already in progress")
            return

        self.host.updating = True
        ret = NetworkPacket()

        #Select datastream compression type
        compress = False
        if "compression" in packet.getFields():
            compTypes = packet.getField("compression").split(b",")
            if b"gzip" in compTypes:
                #Use zlip for compression if we can
                compress = True
            elif not b"plain" in compTypes:
                #can't fall back to plain mode because client doesn't support it
                await sendError(b"compression type not supported.")
                return

        self._logger.debug("Requesting filelist transfer...")
        ret.setOpCode(ret.OP_CONT)
        await self.sendPacket(ret)
        
        filelist = []
        while True:
            packet = await self.receivePacket()
            if packet.opcode == packet.OP_UPDATE_FILELIST:
                self._logger.debug("Received filelist transfer packet")
                try:
                    path = packet.getField("file")
                    hash = packet.getField("hash")
                except:
                    await self.sendError(b"illegal update filelist packet")
                    self.host.updating = False
                    return
                filelist.append([path.decode(), hash])
                ret = NetworkPacket()
                ret.setOpCode(ret.OP_CONT)
                await self.sendPacket(ret)
            elif packet.opcode == packet.OP_NOOP:
                self._logger.debug("Filelist transfer completed.")
                break #Filelist transfer done
            elif packet.opcode == packet.OP_ERROR:
                self.host.updating = False
                return
            else:
                await self.sendError(b"illegal request")
                self.host.updating = False
                return

        #This can take a while but since we shouldn't be doing anything anyways there should not be any problems
            self._logger.debug("Processing filelist...")
        try:
            patchlist = processFileList(filelist)
        except:
            #there was some problem with the filelist, which unfortunately means that we can't continue
            await self.sendError(b"corrupt filelist")
            self.host.updating = False
            return
        ret = NetworkPacket()
        ret.setOpCode(ret.OP_OK)
        await self.sendPacket(ret)

        #Now to the actual tricky part:
        #We want to download the patch data but since the update process can still fail during this step
        #we don't want to download directly into the root directory of the application.
        #Instead, we download into a separate Patch folder that copies the exact filestructure of the
        #application but without most of the files.
        #After the download we shut down the bot, copy everything where it needs to be and then restart it
        #Finally we delete the patch data.

        for entry in patchlist:
            self._logger.debug("Requesting file " + entry)
            #we request a file transfer for every file we have in the patchlist
            ret = NetworkPacket()
            ret.setOpCode(ret.OP_UPDATE_TRANSFER)
            ret.addField("file", entry.encode())
            ret.addField("compression", b"gzip" if compress else b"plain") #Tell the client to use compression if possible
            await self.sendPacket(ret)
            try:
                await self._downloadFile(entry, compress)
            except:
                await self.sendError(b"file download failed, continue")

        #done, send OP_NOOP to shut down the updater on the client. Everything else we will handle on our own from here
        ret = NetworkPacket()
        ret.setOpCode(ret.OP_NOOP)
        await self.sendPacket(ret)
        self._logger.debug("Patch download completed.")

        #actually, if me made it this far we're almost done. Now we hand control over to the host handle, which will copy our patch into the root directory and apply it.
        #Then the application should reboot and load the patch

        self.host.loop.create_task(self.host._applyUpdate(patchlist)) #this will allow the client handle to continue communicating with the RC client

    async def handleConfig(self, packet):

        try:
            cmd = packet.getField("cmd").decode()
        except:
            await self.sendError(b"illegal config packet")
            return

        #Check permissions
        user = self.host.userdb.getUser(self.user)

        if cmd == "status":
            if not user.permissions["viewStatus"]:
                await self.sendError(b"insufficient permission")
                return
            try:
                response = await self.host.getStatus()
            except:
                await self.sendError(b"rpc failed")
                return
            await self.sendPacket(response)
            return

        if cmd == "logs":
            if not user.permissions["viewStatus"]: #we don't have a sophisticated permission for this yet, so we'll just attach it to the status
                await self.sendError(b"insufficient permission")
                return
            try:
                action = packet.getField("action").decode()
            except:
                await self.sendError(b"illegal log config packet")
                return

            if action == "list":
                for i in self.getLogFiles():
                    ret = NetworkPacket()
                    ret.setOpCode(ret.OP_OK)
                    ret.addField("name", i.encode())
                    await self.sendPacket(ret)
                ret = NetworkPacket()
                ret.setOpCode(ret.OP_NOOP) #signal that all packets have been sent
                await self.sendPacket(ret)

            elif action == "open":

                self._logger.debug("loading logfiles...")
                logFiles = self.getLogFiles()
                try:
                    path = packet.getField("name").decode()
                except:
                    await self.sendError(b"illegal log config packet")
                    return

                self._logger.debug("matching requested file...")
                if not (path in logFiles):
                    await self.sendError(b"no such logfile")
                    return

                self._logger.debug("uploading logfile...")
                for i in self.getLogFile(path):
                    ret = NetworkPacket()
                    ret.setOpCode(ret.OP_OK)
                    ret.addField("entry", i.encode())
                    await self.sendPacket(ret)
                self._logger.debug("upload complete.")
                ret = NetworkPacket()
                ret.setOpCode(ret.OP_NOOP) #signal that all packets have been sent
                await self.sendPacket(ret)

        if cmd == "perm":
            if not user.permissions["editPermissions"]:
                await self.sendError(b"insufficient permission")
                return
            try:
                action = packet.getField("action").decode()
            except:
                await self.sendError(b"illegal perm config packet")
                return

            if action == "list":
                #send n packets for n accounts
                allusers = self.host.userdb.getAllUsers()
                for i in allusers:
                    ret = NetworkPacket()
                    ret.setOpCode(ret.OP_OK)
                    ret.addField("name", i.name.encode())
                    for j in i.permissions.items():
                        ret.addField(j[0], struct.pack(">?", j[1]))
                    await self.sendPacket(ret)
                ret = NetworkPacket()
                ret.setOpCode(ret.OP_NOOP) #signal that all packets have been sent
                await self.sendPacket(ret)

            elif action == "create":
                #create a new account and notify the user about success or failure
                try:
                    name = packet.getField("name").decode()
                    key = packet.getField("key")
                except:
                    await self.sendError(b"illegal perm config account creation packet")
                    return

                success = self.host.userdb.createUser(name, key)
                ret = NetworkPacket()
                if success:
                    ret.setOpCode(ret.OP_OK)
                else:
                    ret.setOpCode(ret.OP_ERROR)
                await self.sendPacket(ret)
                return

            elif action == "delete":
                #delete an existing account and notify the user about success or failure
                try:
                    name = packet.getField("name").decode()
                except:
                    await self.sendError(b"illegal perm config account deletion packet")
                    return

                success = self.host.userdb.deleteUser(self.host.userdb.getUser(name))
                ret = NetworkPacket()
                if success:
                    ret.setOpCode(ret.OP_OK)
                else:
                    ret.setOpCode(ret.OP_ERROR)
                await self.sendPacket(ret)
                return

            elif action == "update":
                #update and existing account and notify the user about success or failure
                try:
                    name = packet.getField("name").decode()
                except:
                    await self.sendError(b"illegal perm config account update packet")
                    return

                user = self.host.userdb.getUser(name)

                dict_keys = list(packet.getFields())
                for i in dict_keys:
                    if i == "key":
                        user.key = packet.getField("key")
                    elif i in list(user.permissions.keys()):
                        user.permissions[i] = int(struct.unpack(">?", packet.getField(i))[0])

                success = self.host.userdb.setUser(user)
                ret = NetworkPacket()
                if success:
                    ret.setOpCode(ret.OP_OK)
                else:
                    ret.setOpCode(ret.OP_ERROR)
                await self.sendPacket(ret)
                return

    def getLogFiles(self):

        """
        Enumerate the logfile directory.
        """

        try:
            return os.listdir("logs") #we need to make sure these are properly ordered
        except OSError:
            return []

    def getLogFile(self, path):

        """
        Retrieve the contents of a logfile directory.
        """

        try:
            f = open(os.path.join("logs", path), "r")
            lines = f.readlines()
            f.close()
            return lines
        except OSError:
            return []

    async def mainLoop(self):

        """
        Listen to new commands and check for authentication and authorization
        """

        while True:
            self._logger.debug("Client is waiting for packet...")
            packet = await self.receivePacket()
            self._logger.debug("Client handle received new packet.")
            if not packet:
                self._logger.debug("Client is not responding, closing connection.")
                #client probably disconnected, close handle
                self.disconnect()
                return
            if not (self.is_authenticated or packet.opcode in (packet.OP_NOOP, packet.OP_OK, packet.OP_CONT, packet.OP_ERROR, packet.OP_LOGIN)):
                #Client is not authenticated, refuse action
                self._logger.warning("Unauthenticated client requested action requiring authorization.")
                ret = NetworkPacket()
                ret.setOpCode(ret.OP_ERROR)
                ret.addField("description",b"access denied")
                await self.sendPacket(ret)
                continue

            if packet.opcode == packet.OP_LOGIN:
                await self.handleLogin(packet)
            elif packet.opcode == packet.OP_LOGOUT:
                await self.handleLogout(packet)
                return
            elif packet.opcode == packet.OP_CMD:
                await self.handleCommand(packet)
            elif packet.opcode == packet.OP_RATCMD:
                await self.handleRATCommand(packet)
            elif packet.opcode == packet.OP_UPDATE_INIT:
                await self.handleUpdate(packet)
            elif packet.opcode == packet.OP_CONFIG:
                await self.handleConfig(packet)
            
            elif packet.opcode in (packet.OP_OK, packet.OP_CONT, packet.OP_NOOP):
                continue
            elif packet.opcode == packet.OP_ERROR:
                self._logger.warn("Client sent an OP_ERROR packet")
                continue
            else:
                #Wut?
                self._logger.error("Client sent illegal packet.")
                ret = NetworkPacket()
                ret.setOpCode(ret.OP_ERROR)
                ret.addField("description", b"illegal action")
                await self.sendPacket(ret)
                continue

    def disconnect(self):

        """
        Disconnect handle.
        This method will disconnect the client and prepare the client handle to be GCed.
        It will also automatically dereference itself from the host.
        """

        self._logger.info("Disconnecting...")
        try:
            if self.writer.can_write_eof():
                self.writer.write_eof()
        except:
            pass
        try:
            self.writer.close()
        except:
            pass
        self._logger.debug("Client disconnected, discarding handle")
        self.host.removeClient(self)

    async def receivePacket(self):

        """
        Wait for a packet to be delivered and return it
        """

        try:
            p = await NetworkPacket.fromStream(self.reader)
        except BaseException as e:
            self._logger.error("Failed to receive packet: " + str(e))
            return None
        self._logger.debug("Packet received")
        return p

    async def sendPacket(self, packet):

        """
        Sends a packet to the client
        """

        try:
            self.writer.write(packet.to_bytes())
            await self.writer.drain()
        except BaseException as e:
            self._logger.error("Failed to write to client connection: " + str(e))
            return False
        self._logger.debug("Packet sent")
        return True

class RATHost():

    def __init__(self, loop=None):

        """
        RAT host
        This class represents a wrapper around the application.
        It keeps the app alive and provides convenience features
        such as remote monitoring, administration and updating.
        """

        self._logger = logging.getLogger("RATHost")
        self.loop = loop if loop else asyncio.get_event_loop()
        self._RATsocket = None
        self._RATserver = None
        self.clients = []
        self.maxConnectedClients = 5 #just some default value
        self.running = False #True if the app is currently running
        self.updating = False #True if the updater is downloading or installing a patch
        self.stopping = False #True if the app has been scheduled to stop

        self.runningSince = None
        self.errors = 0

        self._logger.debug("Creating user database handle...")
        self.userdb = DatabaseHandle("Credentials/users.db")

        if not self.userdb.getAllUsers():
            self._logger.debug("No RC account found, performing first time setup")
            self._setUpUAC()

        self._startServer()
        self.loop.create_task(self._runApp())

    def _setUpUAC(self):

        print("WARNING: No user account found. This setup wizard will help you create one.")
        print("This account will be automatically assigned admin permissions. Be aware that you cannot change it's permissions unless there is at least another account with admin permissions.")
        print("")
        username = input("Please enter a username: ")
        password = input("Please enter a password: ")

        #creating key
        pwh = hashlib.sha512()
        pwh.update(password.encode())
        crh = hashlib.sha512()
        crh.update(pwh.digest())
        crh.update(username.encode())

        print("")

        newuser = self.userdb.createUser(username, crh.digest()) #create user
        if not newuser:
            self._logger.error("Unable to create user account, check you logs. Try to elevate program permissions.")
            return False

        success = self.userdb.setPermission(newuser, {
            "viewStatus": 1,
            "runCommands": 1,
            "runRATCommands": 1,
            "update": 1,
            "editPermissions": 1
            })

        if not success:
            self._logger.error("Unable to elevate permissions for admin account.")
            return False

        print("Admin account created! Consider using this account to set up a second admin account, then delete the first one, if other people have access to this machine.")
        return True

    async def _handleClientConnection(self, reader, writer):

        """
        Initialize a new client connection
        This method will constuct a new Client instance to handle communications with the client
        """

        self._logger.info("A new client is trying to connect...")

        #if this throws an error, the connection should be dropped
        if len(self.clients) >= self.maxConnectedClients:
            self._logger.warning("A client tried to connect but the maximum of client connections is already reached.")
            if writer.can_write_eof():
                writer.write_eof()
            writer.close()
            return

        self._logger.info("A new client has connected")
        self.clients.append(Client(self, reader, writer)) #keep a reference to the client
        return

    async def _runApp(self):

        """
        App main loop
        This will keep the app alive UNLESS it is supposed to shut down.
        If the app exits unexpectedly, this method will wait a short period of time and then try to restart it.
        """

        while not self.stopping: #As long as we ain't stopping we running
            self._logger.info("App restarting...")
            try:
                self.running = True
                self.runningSince = time.time()
                await self.loop.run_in_executor(None, functools.partial(subprocess.run,(getInterpreterCommand(), APP_PATH), check=True))
            except subprocess.CalledProcessError as e:

                self.errors += 1
                self._logger.warning("App crashed: " + str(e))#we don't actually care if it was succesfull or not, we determine how to react to a crash by different means
                self._logger.debug(traceback.format_exc())
            except: #if this happens we are fucked and restarting the process would just result in an infinite loop while using a lot of CPU so we just abort

                self._logger.fatal("App could not be started, check your configurations.")
                #self._logger.exception("")
                self.stopping = True
            self.runningSince = None
            self.running = False
            #if this call returns, the app has exited. Why is none of our concern, we just check if it was INTENDED.
            #This is done by looking at the self.stopping flag: if it was set by the host, this means that the app shut down as
            #requested. In this case we just reset the flag and wait. Otherwise we reboot.
            if not self.stopping:
                self._logger.info("App shut down. Restarting in 3 seconds...")
                await asyncio.sleep(3) #This is here to ensure we aren't bombarding the gateway with connection attempts which would eventually lead to a timeout or account termination
        self.stopping = False #this flag should be set every time the app is shut down intentionally. We reset it to prevent the app from having unexpected downtime
        self._logger.info("App has shut down.")
        return

    def _startServer(self):

        """
        Starts the internal server and listens to incoming client connections
        """

        self._logger.info("Preparing RAT server...")
        self._logger.debug("Creating socket/SSL context...")
        if ENABLE_SSL:
            self._logger.debug("SSL is ENABLED, loading certificate file...")
            self._sslContext = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self._sslContext.load_cert_chain(CERT_FILE, CERT_KEY, CERT_PASSW) #load our ssl certificate
            self._logger.debug("Success!")
        else:
            self._logger.warn("SSL is DISABLED. Attackers may be able to read your password when you log in.")
        self._logger.debug("Creating server listener...")
        self._RATserver = asyncio.start_server(self._handleClientConnection, loop=self.loop, host=RAT_HOST, port=RAT_PORT, ssl=self._sslContext if ENABLE_SSL else None)
        self.loop.create_task(self._RATserver)
        self._logger.info("RAT server online, listening for incoming client connections at " + RAT_HOST + ":" + str(RAT_PORT))

    def removeClient(self, client):

        """
        Removes the client instance from the internal reference list so it can be GCed
        """

        if client in self.clients:
            self._logger.debug("Client reference removed")
            self.clients.remove(client)
        return

    async def runCommand(self, cmd):

        """
        Send the command to the app and retrieve its results
        """

        self._logger.debug("Initializing RPC for " + cmd.decode())
        r, w = await asyncio.open_connection("localhost", APP_RC_PORT) #connect to app
        w.write(cmd)
        if w.can_write_eof():
            w.write_eof()
        ret = await r.read(-1)
        try:
            w.close()
        except:
            self._logger.warning("Failed to properly close RPC streams")
            pass #doesn't really matter if these fail, and it will every time the bot is shut down anyways
        self._logger.debug("RPC returned, passing result")
        return ret

    async def stopApp(self):

        """
        Stop the app.
        This method will return None regardless of success
        """

        self._logger.info("Stopping the app...")
        self.stopping = True
        try:
            await self.runCommand(b"quit")
        except:
            self._logger.exception("Stopping the app failed: ")

    async def rebootApp(self):

        """
        Restart the app.
        This method will return None regardless of success
        """

        #This feature will start the app if it has stopped and will soft reboot it if it is running.
        #To execute an actual hard reboot via RC, one should call stop, then reboot after a few seconds.
        #This will ensure that the process is closed completely.

        self._logger.info("Rebooting the app...")
        self.stopping = False
        if self.running:
            try:
                await self.runCommand(b"quit") #if the app is already running we soft reboot it
            except:
                self._logger.exception("Stopping the app failed: ")
        else:
            self.loop.create_task(self._runApp()) #if it isn't, we restart it completely

    async def getStatus(self):

        """
        Returns a NetworkPacket with various status information
        """

        #we want to dynamically create a packet for this feature since it gives the client better control over what to display
        self._logger.debug("Fetching status information...")
        packet = NetworkPacket()
        packet.setOpCode(packet.OP_OK)
        packet.addField("version", S_VERSION.encode())
        if self.updating:
            state = b"updating..."
        elif self.stopping:
            state = b"stopping..."
        elif self.running:
            state = b"running"
        else:
            state = b"stopped"
        packet.addField("state", state)
        packet.addField("localtime", time.asctime(time.localtime(time.time())).encode()) #encode the current time at the location of this machine
        if self.runningSince:
            packet.addField("runningSince", time.asctime(time.localtime(self.runningSince)).encode()) #encode the local time equivalent of the starting time
            packet.addField("runningFor", (str(datetime.timedelta(seconds=time.time() - self.runningSince))).encode()) #encode the time difference since the last restart
        packet.addField("errors", str(self.errors).encode())
        packet.addField("clients", str(len(self.clients)).encode())
        return packet

    async def runRATCommand(self, cmd, user):

        """
        Execute RAT command
        """

        if cmd == b"shutdown":
            await self.stopApp()
            return b"OK"

        elif cmd == b"reboot":
            await self.rebootApp()
            return b"OK"

        return b""

    async def _applyUpdate(self, patchlist):

        """
        Host updater
        This method will shut down the app and apply a previously downloaded patch.
        The app will be automatically restarted afterwards.
        """

        self.updating = True #just to be sure
        await self.stopApp() #shut down the app so it doesn't interfere with the update process

        while self.running:
            await asyncio.sleep(0.2) #wait for process to exit

        self._logger.info("Current directory is %s" % os.getcwd())
        self._logger.info("Installing patch...")
        total = 0
        installed = 0
        for i in patchlist:

            total += 1

            fromPath = (pathlib.PureWindowsPath(PATCH_PATH) / i).as_posix()
            toPath = (pathlib.PureWindowsPath(UPDATE_PATH) / i).as_posix()

            try:
                os.makedirs(os.path.split(toPath)[0], exist_ok=True)
            except:
                #if this fails it doesn't necessarily mean that the file can't be created, for example if the given folder structure already exists.
                self._logger.error("Failed to create directory structure for file '%s'." % toPath)

            self._logger.info("Copying file %s (%s -> %s)" % (i, fromPath, toPath))
            try:
                shutil.copy(fromPath, toPath)
            except:
                self._logger.info("Skipping file at " + i + " - failed to create file object")
                continue

            installed += 1
        self._logger.info("Update complete. Updated " + str(installed) + " of " + str(total) + " file(s) - " + str(total-installed) + " error(s)")
        self._logger.debug("Clearing patch cache...")
        shutil.rmtree(PATCH_PATH, True) #Until we have a better error reporting system, we will ignore all errors this call produces, since it is just clean up and doesn't have any actual importance
        self._logger.debug("Rebooting...")
        await self.rebootApp()
        self.updating = False #again, just to be safe
        return

    def start(self):

        """
        Start the app and the server.
        This call will block
        """

        self.loop.run_forever()

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", action="count", default=0)

    args = parser.parse_args()

    #Only run logging setup if we are running this module
    if args.verbose > 0:
        logging.basicConfig(level=logging.DEBUG)

    logging.config.dictConfig(LOGGING_DICT)

    TheApp = RATHost()
    TheApp.start()
