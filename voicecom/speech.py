import audioop
import asyncio
import json
import functools
import io
import os
import shlex
import uuid
import logging
import subprocess
import wave

HAS_SPEECH = True
try:
    import speech_recognition
    import gtts
except ImportError:
    HAS_SPEECH = False

HAS_MQTT = True
try:
    import gmqtt as mqtt
except ImportError:
    HAS_MQTT = False

class SpeechABC():

    """
    ABC for speech engines (recognition & synthesis)
    Mostly used to manage global constants and variables.
    """

    SAMPLE_RATE = 48000
    SAMPLE_WIDTH = 2

    def __init__(self):

        self.loop = asyncio.get_event_loop()

#=====================================
#SPEECH RECOGNITION
#=====================================

class SpeechRecognitionEngine(SpeechABC):

    async def recognize(self, data):

        return ""

class SphinxRE(SpeechRecognitionEngine):

    def __init__(self):

        if not HAS_SPEECH:
            raise RuntimeError("Speech recognition is not available!")
        super().__init__()

        self._recognizer = speech_recognition.Recognizer()

    async def recognize(self, data):
        mono = audioop.tomono(data, self.SAMPLE_WIDTH, 1, 0)
        audio = speech_recognition.AudioData(mono, self.SAMPLE_RATE, self.SAMPLE_WIDTH)
        return await self.loop.run_in_executor(None, self._recognizer.recognize_sphinx, audio)

class GoogleRE(SpeechRecognitionEngine):

    KEY = "AIzaSyDXG5ub2EuttJ3G1R8ka4DCe9Gq_uyEUNc"

    def __init__(self):

        if not HAS_SPEECH:
            raise RuntimeError("Speech recognition is not available!")
        super().__init__()

        self._recognizer = speech_recognition.Recognizer()

    async def recognize(self, data):
        mono = audioop.tomono(data, self.SAMPLE_WIDTH, 1, 0)
        audio = speech_recognition.AudioData(mono, self.SAMPLE_RATE, self.SAMPLE_WIDTH)
        func = functools.partial(self._recognizer.recognize_google, audio, key=self.KEY)
        return await self.loop.run_in_executor(None, func)

class GoogleCloudRE(SpeechRecognitionEngine):

    CREDENTIALS = None
    KEY = "AIzaSyDXG5ub2EuttJ3G1R8ka4DCe9Gq_uyEUNc"
    
    try:
        CREDENTIALS = open("./config/client_secret2.json", "r").read()    
    except FileNotFoundError:
        pass

    def __init__(self):

        if not HAS_SPEECH:
            raise RuntimeError("Speech recognition is not available!")
        super().__init__()

        self._recognizer = speech_recognition.Recognizer()

    async def recognize(self, data):
        mono = audioop.tomono(data, self.SAMPLE_WIDTH, 1, 0)
        audio = speech_recognition.AudioData(mono, self.SAMPLE_RATE, self.SAMPLE_WIDTH)
        return await self.loop.run_in_executor(None, self._recognizer.recognize_google_cloud, audio, self.CREDENTIALS)

class RhasspyRE(SpeechRecognitionEngine):

    CLIENT_ID = "ram-voice-commands"
    TOKEN = ""

    def __init__(self, address):

        if not HAS_MQTT:
            raise RuntimeError("Not MQTT client installed! Please install paho.mqtt")
        super().__init__()

        self._result_fut = None

        self.address = address
        self._client = mqtt.Client(self.CLIENT_ID)
        self.loop.create_task(self._connect())

    def _msg_callback(self, client, topic, payload, qos, properties):

        if topic == "hermes/asr/textCaptured":

            self._result_fut.set_result(payload)

        elif topic == "hermes/error/asr":

            self._result_fut.set_exception(RuntimeError("Audio transcription failed: %s" % payload))

    async def _connect(self):

        self._client.set_auth_credentials(self.TOKEN, None)
        self._client.on_message(self._msg_callback)
        await self._client.connect(*self.address)
        self._client.subscribe("hermes/asr/textCaptured")
        self._client.subscribe("hermes/error/asr")

    async def recognize(self, data):

        payload = io.BytesIO()
        wave_obj = wave.open(payload, "wb")

        wave_obj.setnchannels(2)
        wave_obj.setsampwidth(self.SAMPLE_WIDTH)
        wave_obj.setframerate(self.SAMPLE_RATE)
        wave_obj.writeframes(data)
        wave_obj.close()

        session = uuid.uuid4().hex
        self._result_fut = asyncio.Future()

        self._client.publish("hermes/asr/startListening", session)
        self._client.publish("hermes/audioServer/default/audioFrame", payload.getvalue())
        self._client.publish("hermes/asr/stopListening", session)

        return await self._result_fut

#=====================================
#SPEECH SYNTHESIS
#=====================================

class SpeechSynthesisEngine(SpeechABC):

    async def synthesize(self, text):

        """
        Synthesize a text phrase. Should return a PCM buffer.
        """

        return b""

def google_tts_to_pcm(buf, sample_rate):

    TEMP_DIR = "./_temp/tts"

    logger = logging.getLogger("GoogleTTSBuffer")

    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR, exist_ok=True)

    _uuid = uuid.uuid4()
    path = os.path.join(TEMP_DIR, "%s.mp3" % _uuid)
    logger.debug("Creating temporary file...")
    with open(path, "wb") as f:
        f.write(buf)

    logger.debug("Creating FFMPEG decoder process...")
    cmd = "ffmpeg -i %s -f s16le -ar %i -ac %i -loglevel warning pipe:1" % (shlex.quote(path), sample_rate, 2)
    process = subprocess.Popen(shlex.split(cmd), stdin=None, stdout=subprocess.PIPE, stderr=None)

    data = b""
    while True:
        newdata = process.stdout.read()
        if len(newdata) < 1:
            break
        data += newdata

    try:
        process.kill()
        if process.poll() is None:
            process.communicate()
    except:
        logger.exception("Error happened while attempting to shut down FFMPEG instance:")

    logger.debug("Cleaning up...")

    try:
        os.remove(path)
    except OSError as e:
        logger.exception("Unable to clean up temporary file: %s" % str(e))

    return data


class GoogleTTS(SpeechSynthesisEngine):

    async def synthesize(self, text):

        func = functools.partial(gtts.tts.gTTS, text)
        #Not quite sure which one of these function calls actually blocks
        #(may as well be both for all I know), so I put two executor calls here.
        tts = await self.loop.run_in_executor(None, func)
        buf = io.BytesIO()
        await self.loop.run_in_executor(None, tts.write_to_fp, buf)
        return google_tts_to_pcm(buf.getvalue(), self.SAMPLE_RATE)
