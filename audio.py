#Discord ProtOS Bot
#
#Author: Jascha "fredi_68" Hirsekorn
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

import discord

READ_BUFFER_SIZE = 1024
SAMPLE_WIDTH = 2

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
        self.skippable = skippable
        self.is_paused = False
        self.is_dead = False

        #Meta information
        self.title = title
        self.author = author
        self.uri = "<empty>"

    def setVolume(self, volume):

        """
        Set the volume of this sound.
        volume should be a float between 0 (muted) and 2 (double volume).
        1 is original volume.
        """

        self.volume = max(min(volume, 2.0), 0)

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
            return audioop.mul(buf, SAMPLE_WIDTH, self.volume)
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

class FFMPEGSound(Sound):

    """
    Class representing an instance of FFMPEG playing a sound.

    This implementation uses lazy ressource loading to save on memory and
    prevent timeouts on remote ressources by only loading the stream right
    before the sound starts playing.

    You need to have the FFMPEG executable in your path in order for
    this class to be available.
    """

    def __init__(self, target, *args, **kwargs):

        Sound.__init__(self, *args, **kwargs)

        self.target = target
        self.process = None

        self.uri = target #ensure target is displayed correctly

    def prepare(self, channel):

        self.logger.debug("Preparing FFMPEG sound to play on channel %s..." % channel.voice_client.channel.name)
        encoder = channel.voice_client.encoder
        cmd = "ffmpeg -i %s -f s16le -ar %i -ac %i -loglevel warning pipe:1" % (shlex.quote(self.target), encoder.sampling_rate, encoder.channels)
        try:
            self.process = subprocess.Popen(shlex.split(cmd), stdin=None, stdout=subprocess.PIPE, stderr=None)
        except FileNotFoundError:
            raise AudioError("FFMPEG was not found.")
        except subprocess.SubprocessError as e:
            self.logger.exception("An error occured while trying to setup FFMPEG process: ")
            raise AudioError("subprocess.Popen failed: %s" % str(e))

    def play(self):

        self.logger.debug("Launching FFMPEG sound instance...")
        if self.process == None:
            raise AudioError("FFMPEG is not setup correctly, please call prepare() before attempting to play this sound.")

    def read(self, n):

        if self.process == None:
            raise AudioError("FFMPEG is not setup correctly, please call prepare() before attempting to play this sound.")

        if not self.is_paused:
            buf = self.process.stdout.read(n)
            if len(buf) < 1:
                self.logger.debug("Sound buffer exhausted, deinitializing...")
                self.kill()

            return self.doVolume(self.doPanning(buf))

    def stop(self):

        self.logger.debug("FFMPEG sound stopping...")
        self.process.kill()
        if self.process.poll() is None:
            self.process.communicate()

        self.kill()
        self.logger.debug("FFMPEG sound stopped.")

class ChannelStream():

    """
    Single channel of audio playback
    This class manages one channel of audio playback and it's associated voice client.
    """

    logger = logging.getLogger("AudioEngine.Channel")

    def __init__(self, voice_client):

        self.channel = voice_client.channel
        self.voice_client = voice_client
        self.volume = 1.0
        self._playing = []
        self._queue = collections.deque()
        self._player = None
        self.rmLock = threading.Lock()

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

    def after(self):

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

        if not self._player or self._player.is_done():
            self._player = self.voice_client.create_stream_player(self, after=self.after)
            self._player.start()

    def cleanUp(self):

        self.rmLock.acquire()
        for i in self._playing.copy():
            if i.is_dead:
                self._playing.remove(i)
        self.rmLock.release()

    def next(self):

        """
        Play the next sound in the queue.
        Sounds that are playing are skipped, unless they are unskippable. In this case,
        the channel will wait until those sounds have completed, then launch the next sound in the queue.
        """

        self.rmLock.acquire()
        for i in self._playing.copy():
            if i.skippable:
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

        #The fuck is this about?
        #print(self.read())
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

    def hasAudio(self):

        """
        Returns True if audio is playing or queued, False otherwise
        """

        return len(self._queue) > 0 or len(self._playing) > 0

    def read(self, n=READ_BUFFER_SIZE):

        """
        Reads up to n bytes from the currently playing sound objects and return as a PCM stream.
        """

        buffer = b""

        self.cleanUp()

        for i in self._playing:
            sa = i.read(n)
            if self.volume != 1.0: #apply channel volume
                sa = audioop.mul(sa, SAMPLE_WIDTH, self.volume)
            if len(sa) > len(buffer):
                buffer += bytes([0] * (len(sa) - len(buffer)))
            elif len(buffer) > len(sa):
                sa += bytes([0] * (len(buffer) - len(sa)))
            buffer = audioop.add(buffer, sa, SAMPLE_WIDTH)

        #only auto skip if we have no sounds and the buffer is empty.
        #if the queue is empty, there is no point in advancing
        if len(buffer) < 1 and len(self._playing) < 1 and len(self._queue) > 0:
            self.logger.debug("Active sounds finished playing, advancing to next item in queue.")
            self.next()
            return self.read(self, n)

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

    def playSound(self, sound, channel, sync=True):

        """
        Plays a sound on the specified channel.
        sound must be an instance of audio.Sound.
        channel must be an instance of discord.Channel and must be a voice channel the bot is currently connected to.
        if sync is True, the sound will be queued and only played once all other sounds on this channel have finished.
        """

        if not hasattr(channel.server, "voice_client") or channel.server.voice_client == None:
            raise AudioError("There is no voice connection on this server.")

        vc = channel.server.voice_client

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

    def skipSound(self, channel):

        """
        Skips the sound currently playing on the specified channel.
        This only works if the queue on the channel is not empty.
        """

        ch = self._getChannelByID(channel.id)
        if not ch.hasAudio():
            raise AudioError("The queue on this channel is empty.")

        ch.next() #skip the currently playing sounds

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
        """

        ch = self._getChannelByID(channel.id)
        return ch.getQueue()

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