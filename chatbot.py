#Discord ProtOS Bot
#
#Author: Jascha "fredi_68" Hirsekorn
#
#MegaHAL chatbot implementation

host = "localhost"
port = 50011
port2 = 50012

import os
import sys
import asyncio
import subprocess
import logging

logging.basicConfig(level=logging.INFO) #set log level
logger = logging.getLogger("MegaHAL")

wd = "bin/megahal"
binpath = "bin/megahal/megahal.exe"

def bytes_in(b):

    """prepare bytestring for AI process"""

    return b.replace(b"\n", b"\r\n")

def bytes_out(b):

    """prepare bytestring for network transfer"""

    return b.replace(b"\r\n", b"\n")

def stripBrackets(b):

    """delete those random brackets from the start of messages. I tried getting rid of them. They keep coming back."""

    while b.startswith(b"> "):
        b = b[2:]
    return b

def readMessage(stream):

    """Read exactly one message from input."""

    answer = b""
    while True: #since we are getting multiline bot answers now, we have to make sure to read until completion, even over multiple lines
        char = stream.read(1) #be fucking careful
        answer += char
        if answer.endswith(b"\r\n> "): #we have to do this to ensure newlines are properly converted
            break
    return answer[:-3]

proc = subprocess.Popen(binpath, stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=False, cwd=wd)
for i in range(0, 11):
    a = proc.stdout.readline() #skip intro

readMessage(proc.stdout) #skip first message

logger.info("Startup sequence successful")

loop = asyncio.get_event_loop()

async def handle_request(reader, writer):

    message = await reader.read(-1)
    if not message:
        #We do not handle empty messages anymore... if it occurs just return a default placeholder
        writer.write(b"There is nothing here...")
        writer.write_eof()
        writer.close()
    else:
        message += b"\n\n"
        proc.stdin.write(bytes_in(message))
        proc.stdin.flush()
        if not message.startswith(b"#"): #fix for commands
            answer = stripBrackets(bytes_out(readMessage(proc.stdout))) #read until completion
        else:
            answer = b"OK" #DO NOT READ ANYTHING since UN seems to suppress the 3 extra characters we usually get...
        writer.write(answer)
        writer.write_eof()
        writer.close()

async def handle_console():

    while True:
        cmd = await loop.run_in_executor(None, input, (""))
        proc.stdin.write(bytes_in(cmd.encode()))
        proc.stdin.flush()
        if cmd in ("#QUIT", "#EXIT"):
            loop.stop()
            AIServer.close()
            return

#set up tasks
logger.info("Starting AI server...")
AIServer = asyncio.start_server(handle_request, host, port, loop=loop)
loop.create_task(AIServer)
logger.info("Starting console loop...")
loop.create_task(handle_console())

#Setup done, start application
logger.info("ProtOS Discord Bot Remote AI/MegaHAL wrapper v2.0.1")
logger.info("----------------------------------------------------\n")
logger.info("Enter MegaHAL commands using the commandline interface")

loop.run_forever()
loop.close()