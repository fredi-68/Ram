import subprocess
import shlex
import json

FILE_NAME = "tracks/CP40.mp3"

cmd = "ffprobe -i %s -select_streams a:0 -show_entries stream=duration -loglevel warning -of json" % shlex.quote(FILE_NAME)
process = subprocess.Popen(shlex.split(cmd), stdin=None, stdout=subprocess.PIPE, stderr=None)
buf = process.stdout.read(-1)
process.kill()

d = json.loads(buf)
print(d)