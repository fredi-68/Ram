import ctypes
import logging
import array

import discord
from discord.opus import _lib, OpusError, c_int16_ptr, log, c_int_ptr

logger = logging.getLogger("OPUS")

#Makeshift opus decoder built on the discord.py opus encoder. Now on to figure out which function I have to call...
#Most code is adapted from discord.opus.Encoder cause I am too lazy to do my own research

HAS_OPUS = True
if not discord.opus.is_loaded():
    #OPUS should already be loaded by the main program, if it isn't it is most likely due to an error. Thus we will skip all the fancy config stuff and just fall back to standard paths.
    logger.warn("OPUS was not loaded on program startup! Attempting to load opus library...")
    try:
        defaultLibPath = "32"
        if platform.architecture()[0] == "64bit": #we've got a 64bit system; since discord.py is very picky about the location and the name of the opus library, change the default to make sure users without a config don't run into problems (at least on windows this should work)
            defaultLibPath = "64"
        discord.opus.load_opus("bin/opus/opus"+defaultLibPath)
    except:
        logger.error("OPUS could not be initialized. Please check your config!")
        HAS_OPUS = False

#TYPES
c_char_ptr = ctypes.POINTER(ctypes.c_char)
c_ubyte_ptr = ctypes.POINTER(ctypes.c_ubyte)
c_int32_ptr = ctypes.POINTER(ctypes.c_int32)

class DecoderStruct(ctypes.Structure):

    pass

DecoderStructPtr = ctypes.POINTER(DecoderStruct)

#Set argtypes:

_lib.opus_decode.argtypes = [DecoderStructPtr, c_char_ptr, ctypes.c_int32, c_int16_ptr, ctypes.c_int, ctypes.c_int]
_lib.opus_decode.restype = ctypes.c_int

_lib.opus_decoder_create.argtypes = [ctypes.c_int, ctypes.c_int, c_int_ptr]
_lib.opus_decoder_create.restype = DecoderStructPtr

_lib.opus_decoder_destroy.argtypes = [DecoderStructPtr]
_lib.opus_decoder_destroy.restype = None

class OpusDecoder(discord.opus.Encoder):

    """
    The makeshift Opus decoder.
    Most methods have been adapted from discord.opus.Encoder,
    I've mostly just changed all the ctypes calls to reference the decoder instead of the encoder functions.
    """

    def decode(self, data, is_lost=False):

        """
        Makeshift opus decoder function. Had to rewrite most of the code of the Decoder.decode() method for this.
        """

        #Sooo... I've been thinking
        #Also been reading the Opus docs multiple times and I now believe that I finally know what is going on:
        #There is a certain framesize of audio packet data in milliseconds that the encoder/decoder expects to compile into one packet
        #However, my experiments with arbitrary amounts of audio data have proven that the encoder does indeed encode all lengths of
        #sample data which led me to belive that the codec could handle variable frame lengths. Which is something I still belive in...
        #...at least for the encoder. Since the decoder always just returns an empty sequence of bytes (just a bunch of zeros) I figure that
        #it is actually WAITING on the remaining sample data to be delivered in subsequent packets, which, of course, in our tests never arrived.
        #TL;DR I got packet size and frame length mixed up. Gonna try this with different lengths of data now
        #EDIT: This worked the whole time. Just had to call the decode method a second time. Likes to keep itself a filled buffer apparently.

        #After digging through the OPUS demo source, I finally figured out how FEC works:
        #We may ONLY EVER set the FEC flag if we encounter a frame that has actually been lost. Otherwise the decoder won't work properly.

        pcm = (ctypes.c_int16 * (self.FRAME_SIZE))() #creating pcm buffer (array of short pointers)
        pcmLength = len(pcm)
        pcm_p = ctypes.cast(pcm, c_int16_ptr)
        
        if data:
            
            #length = ctypes.cast(len(data),ctypes.c_int32) #size of the audio packet, put it into a pointer
            length = len(data)

        else:
            #length = ctypes.cast(0,ctypes.c_int32) #This is in case the encoder has to deal with packet loss, in which case we send a None value
            length = 0

        ret = _lib.opus_decode(self._state, data, length, pcm_p, self.FRAME_SIZE, 1 if is_lost else 0) #ONLY set FEC flag if we are experiencing actual packet loss
        if ret < 0: #The usual error checking...
            log.info('error has happened in decode')
            raise OpusError(ret)

        #Further adjust this if necessary, but be VERY CAREFUL since exceeding array boundaries can result in application hangs and crashes.
        return array.array('h', pcm[:self.FRAME_SIZE//2]).tobytes() #changing the array limit was the key, decoder works now. However, the tie-in to Discord does not.

    def __del__(self):

        """
        This is where the encoder/decoder is destroyed.
        """

        if hasattr(self, '_state'):
            _lib.opus_decoder_destroy(self._state)
            self._state = None

    def _create_state(self):
        
        """
        This is where the encoder/decoder is created. We need to switch this to make decoding possible.
        """

        #Works. Can't believe it myself but it works.
        ret = ctypes.c_int()
        result = _lib.opus_decoder_create(self.SAMPLING_RATE, self.CHANNELS, ctypes.byref(ret))

        if ret.value != 0:
            log.info('error has happened in state creation')
            raise OpusError(ret.value)

        return result

    def set_bitrate(self, kbps):
        
        return 0 #Not implemented for Opus Decoder

    def set_bandwidth(self, req):
        
        return 0 #Not implemented for Opus Decoder

    def set_signal_type(self, req):
        
        return 0 #Not implemented for Opus Decoder

    def set_fec(self, enabled=True):
        
        return 0 #Not implemented for Opus Decoder

    def set_expected_packet_loss_percent(self, percentage):
        
        return 0 #Not implemented for Opus Decoder