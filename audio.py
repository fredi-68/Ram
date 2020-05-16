#Discord ProtOS Bot
#
#Author: fredi_68
#
#Audio Engine
#For when discord.py's audio engine just doesn't cut it anymore.
#Supports serial and parallel audio playback on the same channel,
#unlimited channel count, lazy resource loading, multi stage
#panning and volume control, priority queueing and more.

import logging
import audioop
import collections
import shlex
import subprocess
import threading
import json
import random
import uuid
import urllib
import os
import enum
import io

import discord
from discord.player import AudioPlayer
from discord.opus import Encoder

from version import S_TITLE_VERSION

READ_BUFFER_SIZE = 1024
DOWNLOAD_BUFFER_SIZE = 4096
SAMPLE_WIDTH = 2

class LoopMode(enum.Enum):

    NONE = 0
    SONG = 1
    QUEUE = 2

class AudioError(Exception):

    pass

class Sound():

    """
    ABC for playable sound objects.
    This is an abstract class. Do not instanciate it directly.
    """

    logger = logging.getLogger("AudioEngine.Sound")

    def __init__(self, *args, volume=1.0, panning=0.0, skippable=True, title="Untitled", author="Unknown"):

        self.setVolume(volume)
        self.setPanning(panning)
        self.setTransition(1)
        self.skippable = skippable
        self.is_paused = False
        self.is_dead = False

        #Meta information
        self.title = title
        self.author = author
        self.uri = "<empty>"

        #used for auto crossfade feature.
        #offset should be set to the amount of audio frames that have been played so far.
        #duration should be the total length of the sound, in frames.
        #if duration is unknown or cannot be determined, it should be set to a negative value.
        self.duration = -1 
        self.offset = 0

    def setVolume(self, volume):

        """
        Set the volume of this sound.
        volume should be a float between 0 (muted) and 2 (double volume).
        1 is original volume.
        """

        self.volume = max(min(volume, 2.0), 0)

    def setTransition(self, volume):

        """
        Used by the auto crossfade feature.
        Sets the transition volume to the specified amount. The default is 1.
        The transition volume works like an additional volume separate from the normal sound volume.
        It should not be accessible to the user, use setVolume for all volume related actions.
        volume should be a float between 0 (off) and 1 (unaltered).
        """

        self.transitionVolume = max(min(volume, 1.0), 0)

    def setPanning(self, panning):

        """
        Set the panning of the sound.
        panning should be a float between -1 (left) and 1 (right).
        0 is centered.
        """

        self.panning = max(min(panning, 1), -1)

    def doVolume(self, buf):

        """
        Calculate volume level for the specified buffer.
        Will return a new bytes-like object of the same length as buf.
        """

        if self.volume != 1.0:
            buf = audioop.mul(buf, SAMPLE_WIDTH, self.volume)
        if self.transitionVolume != 1.0:
            buf = audioop.mul(buf, SAMPLE_WIDTH, self.transitionVolume)
        return buf

    def doPanning(self, buf):

        """
        Calculate panning levels for the specified buffer.
        Will return a new bytes-like object of the same length as buf.
        """

        if self.panning == 0.0:
            return buf

        left = audioop.tomono(buf, SAMPLE_WIDTH, 1, 0)
        right = audioop.tomono(buf, SAMPLE_WIDTH, 0, 1)

        left = audioop.mul(left, SAMPLE_WIDTH, (self.panning-1)/2)
        right = audioop.mul(right, SAMPLE_WIDTH, (self.panning+1)/2)

        left = audioop.tostereo(left, SAMPLE_WIDTH, 1, 0)
        right = audioop.tostereo(right, SAMPLE_WIDTH, 0, 1)

        return audioop.add(left, right, SAMPLE_WIDTH)

    def prepare(self, channel):

        """
        Called when the sound is removed from the queue, right before it is played.
        Use this method to fetch any resources you will need to play the sound.
        """

        pass

    def play(self):

        """
        Called after the sound has been added to the playing sound list.
        After this method is called, read() will be called in regular intervals
        until stop is called or the channel is paused.
        """

        pass

    def pause(self):

        self.is_paused = not self.is_paused

    def stop(self):

        """
        Called after the sound has been removed from the queue. Use this to deinitialize all your resources.
        """

        pass

    def kill(self):

        """
        Call this method to signal the audio engine that your sound has finished playing.
        """

        self.is_dead = True

    def read(self, n):

        """
        This method is called in regular intervals after play() has been called. It should return a bytes-like
        object of at most length n. 
        """

        return b""

class PCMSound(Sound):

    def __init__(self, buffer, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.buffer = io.BytesIO(buffer)

    def read(self, n):

        data = self.buffer.read(n)
        if len(data) < 1:
            self.stop()
            self.kill()
        return data

class FFMPEGSound(Sound):

    """
    Class representing an instance of FFMPEG playing a sound.

    This implementation uses lazy resource loading to save on memory and
    prevent timeouts on remote resources by only loading the stream right
    before the sound starts playing.

    You need to have the FFMPEG executable in your path in order for
    this class to be available.
    """

    def __init__(self, target, *args, **kwargs):

        Sound.__init__(self, *args, **kwargs)

        self.target = target
        self.process = None

        self.uri = target #ensure target is displayed correctly

    def _create_player(self, sampling_rate, channel_count):

        self.logger.debug("Creating transcoder process...")
        cmd = "ffmpeg -i %s -f s16le -ar %i -ac %i -loglevel warning pipe:1" % (shlex.quote(self.target), sampling_rate, channel_count)
        try:
            process = subprocess.Popen(shlex.split(cmd), stdin=None, stdout=subprocess.PIPE, stderr=None)
        except FileNotFoundError:
            raise AudioError("FFMPEG was not found.")
        except subprocess.SubprocessError as e:
            self.logger.exception("An error occured while trying to setup FFMPEG process: ")
            raise AudioError("subprocess.Popen failed: %s" % str(e))

        return process

    def _probe_target(self, sampling_rate, channel_count):

        self.logger.debug("Probing target...")
        cmd = "ffprobe -i %s -select_streams a:0 -show_entries stream=duration -loglevel warning -of json" % shlex.quote(self.target)
        try:
            process = subprocess.Popen(shlex.split(cmd), stdin=None, stdout=subprocess.PIPE, stderr=None)
        except FileNotFoundError:
            raise AudioError("FFMPEG was not found.")
        except subprocess.SubprocessError as e:
            self.logger.exception("An error occured while probing the source file: ")
            return

        buf = process.stdout.read(-1)
        if process.poll() == None:
            process.communicate()
        process.kill()

        self.logger.debug("Processing metadata...")
        d = json.loads(buf)
        self.duration = int(channel_count * sampling_rate * float(d["streams"][0].get("duration", -1))) #convert duration to samples

    def prepare(self, channel):

        self.logger.debug("Preparing FFMPEG sound to play on channel %s..." % channel.voice_client.channel.name)
        self._probe_target(Encoder.SAMPLING_RATE, Encoder.CHANNELS)
        self.process = self._create_player(Encoder.SAMPLING_RATE, Encoder.CHANNELS)

    def play(self):

        self.logger.debug("Launching FFMPEG sound instance...")
        if self.process == None:
            raise AudioError("FFMPEG is not setup correctly, please call prepare() before attempting to play this sound.")

    def read(self, n):

        if self.process == None:
            raise AudioError("FFMPEG is not setup correctly, please call prepare() before attempting to play this sound.")

        if not self.is_paused:
            buf = self.process.stdout.read(n)
            l = len(buf)
            self.offset += l #increment offset so the audio engine knows where we are
            if l < 1:
                self.logger.debug("Sound buffer exhausted, deinitializing...")
                self.offset = self.duration
                self.stop() #make sure we deinitialize properly, just calling kill() here skips the entire FFMPEG shutdown process

            return self.doVolume(self.doPanning(buf))

    def stop(self):

        if self.is_dead:
            return

        self.logger.debug("FFMPEG sound stopping...")
        if self.process != None:
            #Sound still in queue
            self.process.kill()
            if self.process.poll() is None:
                self.process.communicate()

        self.kill()
        self.logger.debug("FFMPEG sound stopped.")

class WebResourceSound(FFMPEGSound):

    TEMP_DIR = "_temp/audio"
    USER_AGENT = S_TITLE_VERSION

    def __init__(self, target, *args, **kwargs):

        """
        Create a new WebResourceSound instance.
        ASYNCIO WARNING:
        It is recommended to run this constructor using
        an executor when calling from the main thread since
        the resource download could take some time and
        potentially stall the application.
        """

        self._cleanup_done = False

        #Download remote resource, then change target
        temp_dir = kwargs.get("temp_dir", self.TEMP_DIR)

        os.makedirs(temp_dir, exist_ok=True) #make temporary directory if it doesn't already exist
        
        #make a temporary filename
        filename = uuid.uuid1().hex
        self.filename = os.path.join(temp_dir, filename)

        self.logger.debug("Downloading resource...")
        
        req = urllib.request.Request(target, headers={"User-Agent": self.USER_AGENT})
        res = urllib.request.urlopen(req)

        with open(self.filename, "wb") as f:
            while True:
                d = res.read(DOWNLOAD_BUFFER_SIZE)
                if not d:
                    break
                f.write(d)

        self.logger.debug("Download complete. Creating FFMPEGSound...")

        super().__init__(self.filename, *args, **kwargs)
        self.uri = target #FFMPEGSound would mess up here since it doesn't know we are actually queueing a local copy

    def stop(self):

        #Wait for FFMPEG to finish/stop
        super().stop()

        #clean up temp storage
        self.logger.debug("Removing temporary audio files...")
        try:
            os.remove(self.filename)
        except OSError as e:
            self.logger.warn("Unable to remove temporary local audio file: %s" % str(e))
        self._cleanup_done = True

    def __del__(self):

        if not self._cleanup_done:
            self.logger.warn("Instance did not clean up properly. Attempting to remove temporary files...")
            try:
                os.remove(self.filename)
            except OSError as e:
                self.logger.warn("Unable to remove temporary local audio file: %s" % str(e))
            self._cleanup_done = True

class ChannelStream(discord.AudioSource):

    """
    Single channel of audio playback
    This class manages one channel of audio playback and it's associated voice client.

    ChannelStream inherits from discord.AudioSource because it is needed for the underlying
    audio player to function properly (since this code has to circumvent discord.py's own
    audio system to a degree).
    """

    logger = logging.getLogger("AudioEngine.Channel")

    def __init__(self, voice_client):

        self.channel = voice_client.channel
        self.voice_client = voice_client
        self.volume = 1.0
        self.crossfade = False
        self.crossfadeDuration = 5
        self.crossfadeSamples = Encoder.SAMPLING_RATE * self.crossfadeDuration
        self._playing = []
        self._queue = collections.deque()
        self._player = None
        self.rmLock = threading.Lock()
        self.loopMode = LoopMode.NONE

    def setVolume(self, volume):

        """
        Set the playback volume for this channel.
        THIS WILL AFFECT ALL SOUNDS PLAYING ON THIS CHANNEL,
        REGARDLESS OF INDIVIDUAL SOUND LEVELS
        """

        self.volume = max(min(volume, 2.0), 0)

    def pause(self):

        """
        Pause/Unpause audio playback on this channel.
        """

        if self._player:
            if self._player.is_playing():
                self._player.pause()
            else:
                self._player.resume()

    def after(self, error):

        self.cleanUp()
        self.refreshPlayer()

    def refreshPlayer(self):

        """
        Restarts the discord.py stream player that handles audio playback via network.
        If sounds are queued or playing and the channel detects that the player has shut down,
        it will automatically restart it.
        """

        if not self._playing:
            if len(self._queue) < 1:
                return

        if (self._player is None) or self._player._end.is_set():
            #here we hack into the discord.py voice client to get the AudioPlayer object,
            #which is necessary for our channel stream to control audio playback.
            self.voice_client.play(self, after=self.after)
            self._player = self.voice_client._player

    def cleanUp(self):

        self.rmLock.acquire()
        for i in self._playing.copy():
            if i.is_dead:
                self._playing.remove(i)
        self.rmLock.release()

    def skip(self, index=0, force=False):

        """
        Skip the currently playing sound or a sound from the queue.
        If index is 0, all currently playing sounds are skipped.
        If index is > 0, the sound in the queue at position index - 1
        is removed from the queue instead.
        If force is True, all sounds, even if unskippable, will be skipped.
        Otherwise, only skippable sounds will be affected.
        """

        if index < 1:
            #skip current sound
            self.next(force)
            return

        #skip from queue, make sure it is not empty
        if len(self._queue) < 1:
            raise AudioError("Queue is empty.")

        if index == 1:
            #delete first element
            self.rmLock.acquire()
            self._queue.popleft()
            self.rmLock.release()

        else:
            #delete nth element
            index -= 1
            self.rmLock.acquire()
            self._queue.rotate(-index)
            self._queue.popleft()
            self._queue.rotate(index)
            self.rmLock.release()

    def next(self, force=False):

        """
        Play the next sound in the queue.
        Sounds that are playing are skipped, unless they are unskippable. In this case,
        the channel will wait until those sounds have completed, then launch the next sound in the queue.
        If force is True, the next sound in queue will start playing immediately. All other sounds are
        stopped, even if unskippable.
        """

        self.rmLock.acquire()
        for i in self._playing.copy():
            if i.skippable or force:
                i.stop()
                self._playing.remove(i)
        self.rmLock.release()

        if self._playing:
            return False #need to wait for unskippable sounds to finish

        if len(self._queue) < 1:
            return False
        next = self._queue.popleft()
        self._playing.append(next)
        next.prepare(self)
        next.play()
        self.refreshPlayer()

        return True

    def playSoundSynchroneous(self, sound):

        """
        Place a sound in the queue and play it once the channel is free.
        """

        self._queue.append(sound)
        if not self._playing:
            self.next()

    def playSoundAsynchroneous(self, sound):

        """
        Play a sound in the channel immediately. 
        Audio will be mixed with all sounds that are currently playing.
        """

        sound.prepare(self)
        sound.play()
        self._playing.append(sound)
        self.refreshPlayer()

    def getQueue(self):

        """
        Returns a copy of the internal audio queue, as a list.
        """

        return list(self._queue)

    def getPlaying(self):

        """
        Returns a copy of the internal list of currently active sounds.
        """

        return self._playing.copy()

    def isPaused(self):

        """
        Check if this channel is paused.
        """

        return not self._player.is_playing()

    def hasAudio(self):

        """
        Returns True if audio is playing or queued, False otherwise
        """

        return len(self._queue) > 0 or len(self._playing) > 0

    def read(self, n=-1):

        """
        Reads up to n bytes from the currently playing sound objects and return as a PCM stream.
        """

        if n < 1:
            n = self.voice_client.encoder.FRAME_SIZE

        buffer = b""

        self.cleanUp()

        for i in self._playing:
            sa = i.read(n)
            l_sa = len(sa)
            l_buf = len(buffer)
            if self.volume != 1.0: #apply channel volume
                sa = audioop.mul(sa, SAMPLE_WIDTH, self.volume)
            if l_sa > l_buf:
                buffer += bytes([0] * (l_sa - l_buf))
            elif l_buf > l_sa:
                sa += bytes([0] * (l_buf - l_sa))
            buffer = audioop.add(buffer, sa, SAMPLE_WIDTH)

        #only auto skip if we have no sounds and the buffer is empty.
        #if the queue is empty, there is no point in advancing
        if len(buffer) < 1 and len(self._playing) < 1:
            if len(self._queue) > 0:
                self.logger.debug("Active sounds finished playing, advancing to next item in queue.")
                self.next()
                return self.read(self, n)
            else:
                self.logger.debug("Queue completed, stopping playback.")
                return bytes([0] * 20) #send 5 frames of silence to ensure the encoder is left in the correct state

        return buffer

    def playSound(self, sound, sync=True):

        """
        Play a sound on this channel.
        sound should be an instance of audio.Sound.
        if sync is True, the sound will be queued and only played once all other sounds on this channel have finished.
        """

        if sync:
            return self.playSoundSynchroneous(sound)
        return self.playSoundAsynchroneous(sound)

    def shuffle(self):

        """
        Randomizes the queue.
        """

        self.rmLock.acquire()
        self._queue = collections.deque(random.sample(self._queue, len(self._queue))) #create a random list from the elements of the queue, turn it into a deque
        self.rmLock.release()

    def clear(self, force=False):

        """
        Clears the queue.
        """

        self.rmLock.acquire()

        self._queue.clear()

        for i in self._playing.copy():
            if i.skippable or force:
                i.stop()
                self._playing.remove(i)

        self.rmLock.release()

    def shutdown(self):

        """
        Stops ALL sounds.
        """

        if self._player != None:
            self._player.stop()

        for i in self._queue:
            i.stop()
        self._queue.clear()

        for i in self._playing:
            i.stop()
        self._playing.clear()

class AudioManager():

    """
    Global audio playback manager.
    This class manages all voice clients transmitting audio in the current session.
    Sounds can be queued on ANY channel by calling the playSound() method. If there
    is a voice client associated with the specified channel, a ChannelStream will
    be created and cached automatically.
    """

    logger = logging.getLogger("AudioEngine")

    def __init__(self, client):

        self.client = client
        self.channels = {}

    def createChannel(self, channel):

        """
        Create a new ChannelStream for this channel.
        Return the initialized ChannelStream instance associated with this voice client.
        If a ChannelStream already exists for this channel, it is returned instead.
        If no voice client was found on this server, AudioError will be raised.
        """

        try:
            return self._getChannelByID(channel.id)
        except AudioError:
            try:
                cs = ChannelStream(channel.guild.voice_client)
            except AttributeError:
                raise AudioError("No voice client associated with this server.")
            self.channels[channel.id] = cs
            return cs

    def playSound(self, sound, channel, sync=True):

        """
        Plays a sound on the specified channel.
        sound must be an instance of audio.Sound.
        channel must be an instance of discord.Channel and must be a voice channel the bot is currently connected to.
        if sync is True, the sound will be queued and only played once all other sounds on this channel have finished.
        """

        if not hasattr(channel.guild, "voice_client") or channel.guild.voice_client == None:
            raise AudioError("There is no voice connection on this server.")

        vc = channel.guild.voice_client

        if not channel.id == vc.channel.id:
            raise AudioError("Not currently connected to this channel.")

        if not channel.id in self.channels:
            self.logger.debug("Creating ChannelStream instance for channel %s", channel.name)
            self.channels[channel.id] = ChannelStream(vc)

        self.logger.debug("Playing sound...")
        return self.channels[channel.id].playSound(sound, sync)

    def _getChannelByID(self, ID):

        if not ID in self.channels:
            raise AudioError("There is no audio being transmitted on this channel.")
        return self.channels[ID]

    def skipSound(self, channel, index=0, force=False):

        """
        Skips the sound currently playing on the specified channel.
        This only works if the queue on the channel is not empty.
        If force is True, unskippable sounds will be skipped as well.
        """

        ch = self._getChannelByID(channel.id)
        if not ch.hasAudio():
            raise AudioError("The queue on this channel is empty.")

        ch.skip(index, force)

    def pauseSound(self, channel):

        """
        Pauses or unpauses audio playback on the specified channel.
        """

        ch = self._getChannelByID(channel.id)
        if not ch.hasAudio():
            raise AudioError("The queue on this channel is empty.")

        return ch.pause()

    def getQueue(self, channel):

        """
        Returns the queue of the specified channel, as a list.

        This does NOT include the currently playing sound(s), use
        getPlaying() for that.
        """

        ch = self._getChannelByID(channel.id)
        return ch.getQueue()

    def getPlaying(self, channel):

        """
        Returns a list of currently playing sounds.
        The list may include synchronous or asynchronous sounds.
        """

        ch = self._getChannelByID(channel.id)
        return ch.getPlaying()

    def isPaused(self, channel):

        """
        Check if audio playback is paused.
        """

        ch = self._getChannelByID(channel.id)
        return ch.isPaused()

    def shutdownChannel(self, channel):

        """
        Stops playback on the specified channel.
        This will force skip ALL playing and queued sounds, even if they are
        unskippable.
        """

        ch = self._getChannelByID(channel.id)
        return ch.shutdown()
    
    def setVolume(self, channel, volume):

        """
        Set the volume of the specified channel.
        This will set the volume of the audio playback on the entire channel,
        which means it will affect ALL sounds playing on it, even if they are
        queued. This audio level is separate from the Sound specific audio
        volume. To change playback volume of a sound, use the provided methods
        on the Sound object instead.
        """

        ch = self._getChannelByID(channel.id)
        return ch.setVolume(volume)

    def clearQueue(self, channel, force=False):

        """
        Clears the entire queue and skips all currently playing sounds.
        If force is True, skippable sounds are also skipped.
        """

        ch = self._getChannelByID(channel.id)
        ch.clear(force)

    def shuffleQueue(self, channel):

        """
        Randomizes the queue.
        Does not affect currently playing sounds.
        DOES affect unskippable sounds.
        """

        ch = self._getChannelByID(channel.id)
        ch.shuffle()
