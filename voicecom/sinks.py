import logging
import wave
import audioop
import time

from .constants import *

class AudioSink():

    """
    Base class for audio sinks.

    An audio sink is an object that takes audio data and
    does something useful with it.
    """

    SAMPLE_RATE = 48000
    SAMPLE_WIDTH = 2
    CHANNELS = 2

    logger = logging.getLogger("Voicecom.AudioSink")

    def write(self, data, user):

        """
        Called each time a frame of audio data is received.
        data is the audio, provided as 48khz interleaved stereo le16 PCM.
        user is the instance of the user the audio was recorded from.
        This method should not return anything.
        """

class SimpleFileRecorder(AudioSink):

    """
    Simple audio file recorder. Supports multiple speakers.
    """

    def __init__(self, path):

        self.path = path
        self._files = {}
        self.is_closed = False

    def _create_file(self, user):

        name = getattr(user, "name", "all")
        path = "%s_%s.wav" % (self.path, name)
        f = wave.open(path, "w")
        f.setframerate(self.SAMPLE_RATE)
        f.setnchannels(self.CHANNELS)
        f.setsampwidth(self.SAMPLE_WIDTH)
        self._files[name] = f

    def close(self):

        for f in self._files.values():
            f.close()
        self.is_closed = True

    def write(self, data, user):
        
        name = getattr(user, "name", "all")
        if not name in self._files:
            self._create_file(user)
        f = self._files[name]

        f.writeframes(data)

    def __del__(self):

        if not self.is_closed:
            try:
                self.close()
            except:
                pass

class ReplayBuffer(AudioSink):

    """
    Caches a downmix of all audio in memory.
    Every time the save() method is called, the buffer is
    cleared and the content is returned.
    """

    #The time delta threshold, in samples.
    #The higher this value, the less artifacting, but also less acurate
    DELTA_THRESHOLD = JITTER_THRESHOLD

    def __init__(self, length=20):

        self.length = length
        self.samples = self.SAMPLE_RATE * self.CHANNELS * length * 2
        self._start_time = time.time()
        self.times = {}
        self.buffers = {} 

    def save(self):

        data = b""

        for b in self.buffers.values():
            new_len = len(data)
            src_len = len(b)

            if new_len > src_len:
                #pad source
                b += bytes([0] * (new_len - src_len))
            elif src_len > new_len:
                #pad target
                data += bytes([0] * (src_len - new_len))

            data = audioop.add(data, b, 2)

        self.times.clear()
        self.buffers.clear()
        self._start_time = time.time()

        return data

    def _write(self, data, user):

        """
        Helper method.
        Writes the time corrected stream to the buffer
        """

        if not user in self.buffers:
            self.buffers[user] = b""

        self.buffers[user] += data

        #truncate data
        l = len(self.buffers[user])
        if l > self.samples:
            self.buffers[user] = self.buffers[user][l-self.samples:]

    def write(self, data, user):

        #Here's how this works:
        #Each time we receive a bit of data for a user, the current time is stored.
        #This time is then used to calculate the silence period between speaking.
        #In practice, this means that we need to determine the current time, compute
        #the delta from the stored timestamp, then align it to the samplerate and finally
        #insert the required amount of silence into the users buffer. Retrieving the data
        #merges all streams and returns the combined stream

        if not user in self.times:
            self.times[user] = self._start_time

        t = time.time()
        delta = (t - self.times[user]) * self.SAMPLE_RATE
        self.logger.debug("Replay DELTA is %f" % delta)
        if delta < self.DELTA_THRESHOLD * 2:
            delta = 0 #we got a very small value, set delta to 0 to prevent artifacting
        else:
            self.logger.warning("Compensating for latency")

        data = bytes([0] * int(delta) * 4) + data

        self._write(data, user)

        #set new timestamp
        self.times[user] = t

class SpeechRecognitionBuffer(AudioSink):

    """
    Caches a stream of all audio in memory.
    Each time a STOP SPEAKING event is received, 
    the buffer is cleared and its content is returned.
    """

    def __init__(self):

        self.buffers = {}

    def get_audio(self, user):

        name = user.name
        if not name in self.buffers:
            self.logger.debug("No buffer for user '%s', returning empty buffer object." % name)
            return b""
        data = self.buffers[name][:]
        self.buffers[name] = b""
        return data

    def write(self, data, user):

        name = user.name
        if not name in self.buffers:
            self.buffers[name] = data
            return
        self.buffers[name] += data