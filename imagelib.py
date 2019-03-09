#Discord ProtOS Bot
#
#Author: fredi_68
#
#Image manipulation library
#THIS MODULE AND ITS FUNCTIONALITY IS OPTIONAL
#AND DEPENDS ON THE PYGAME MULTIMEDIA LIBRARY

import logging
import os
import io
import struct
import zlib
import urllib
import ssl

import discord

import version

logger = logging.getLogger("ImageLib")

HAS_PYGAME = True
IS_INIT = False
_display = None
BITMASKS = (0xFF << 0, 0xFF << 8, 0xFF << 16, 0xFF << 24) #pygames default pixel format is BGRA, change it to RGBA, which is PNG channel order

class ImagelibError(Exception):

    """
    Base class for all errors raised by this library.
    """

    pass

class NotInitializedError(ImagelibError):

    """
    Error raised if an attempted call to this library failed due to
    the module not being initialized correctly.
    """

    pass

class SourceError(ImagelibError):

    """
    Error raised if loading an external resource failed.
    This error may be caused by another error raised by a call to the underlying library.
    """

    pass

def init(do_raise = False):

    """
    Initializes the graphics library.
    This function must be called before any other call to this module.
    Failing in doing so will result in a NotInitializedError.
    """

    global HAS_PYGAME
    global IS_INIT
    global pygame

    if IS_INIT:
        return True

    logger.debug("Loading pygame...")
    try:
        import pygame
    except ImportError:
        logger.error("Error while initializing imagelib: Pygame package is not available.")
        HAS_PYGAME = False
        if do_raise:
            raise
        return

    os.environ["SDL_VIDEODRIVER"] = "dummy" #make sure the display works on headless servers

    logger.debug("Initializing libraries...")
    try:
        pygame.init()
    except pygame.error as e:
        logger.error("Error while initializing pygame: " + str(e))
        HAS_PYGAME = False
        if do_raise:
            raise
        return
    
    logger.debug("Initializing display...")

    global _display

    try:
        _display = pygame.display.set_mode((1, 1), 0, 24) #we use 8bit color depth for our encoder so we need to set pygame to 8bit as well
    except pygame.error as e:
        logger.error("Error while initializing display: " + str(e))
        HAS_PYGAME = False
        if do_raise:
            raise
        return

    IS_INIT = True

    return True

def normalizeFilename(path):

    """
    Return the filename extracted from path with the extension changed to PNG so that discord understands it
    """

    fn = os.path.split(path)[1]
    return fn.rsplit(".", 1)[0] + ".png"

def convert(surf):

    """
    Return a copy of surf with the proper pixel format as used by imagelib.
    """

    return surf.convert(BITMASKS)

def loadImage(path):

    """
    Load an image and return it as an Image object.
    """

    if not HAS_PYGAME:
        raise NotInitializedError("Can't open file: Library is not initialized.")

    if not os.path.isfile(path):
        raise ValueError("path is not a valid path")

    surf = pygame.image.load(path).convert(BITMASKS)
    return Image.fromSurface(surf, normalizeFilename(path))

def fromURL(url):

    """
    Returns the image located under the specified URL.
    """

    req = urllib.request.Request(url)
    req.add_header("User-Agent", version.S_TITLE_VERSION) #Silly Discord blocking user agents, this ain't 2002 motherfuckers
    res = urllib.request.urlopen(req)
    try:
        surf = pygame.image.load(io.BytesIO(res.read())).convert(BITMASKS)
    except pygame.error as e:
        logger.error("Error occured while trying to load image from source: " + str(e))
        raise SourceError("Unable to load image: " + str(e))

    return Image.fromSurface(surf, normalizeFilename(url))

def fromUserProfile(user):

    """
    Returns the users profile picture as an image.
    If the user has no avatar, the default avatar is returned.
    """

    if not HAS_PYGAME:
        raise NotInitializedError("Can't load image: Library is not initialized.")

    if not isinstance(user, discord.User):
        raise TypeError("User must be of type discord.User")

    url = user.avatar_url if user.avatar_url else user.default_avatar_url #prefer the actual avatar, fall back to default
    logger.debug("Retrieving avatar...")
    return fromURL(url)

def getPNGChunk(type, payload):

    """
    Create a PNG chunk using the specified type and payload.
    Computes length delimiter and CRC checksum automatically.
    """

    crc = zlib.crc32(type + payload)
    chunk = type + payload
    return struct.pack("!I", len(payload)) + chunk + struct.pack("!I", crc)

def getPNGBuffer(surf):

    """
    Create a PNG file from a surface.
    """

    #Alright, INCREDIBLY INEFFICIENT PURE PYTHON CONVERTER IMPLEMENTATION GO!!!

    #Header:
    #0x89 0x50 0x4E 0x47 0x1A 0x0A

    out = bytes((137, 80, 78, 71, 13, 10, 26, 10))

    #IHDR Chunk
    #Width, Height, BitDepth(8), ColorMode(RGB, 2), Compression(0), Filter(0), Interlace(0)
    
    out += getPNGChunk(b"IHDR", struct.pack("!II", surf.get_width(), surf.get_height()) + bytes((8, 6, 0, 0, 0)))

    #sRGB Chunk

    out += getPNGChunk(b"sRGB", b"\x00")

    #gAMA Chunk

    out += getPNGChunk(b"gAMA", struct.pack("!I", 45455))

    #pHYs Chunk

    out += getPNGChunk(b"pHYs", struct.pack("!II", surf.get_width(), surf.get_height()) + b"\x00")

    #sBIT Chunk

    out += getPNGChunk(b"sBIT", b"\xFF\xFF\xFF\xFF")

    #IDAT Chunk

    comp = zlib.compressobj(level=-1, wbits=15, strategy=zlib.Z_DEFAULT_STRATEGY)
    #chunkPayload = comp.compress(bytes(surf.get_view("3")))

    surfBuffer = bytes(surf.get_buffer())
    chunkPayload = b""

    #Because each scanline needs a filter byte, we need to process every line separately (this is slow, but
    #right now I don't know of a better way to do this)

    scanlineSize = surf.get_width()*4
    for i in range(surf.get_height()):
        chunkPayload += comp.compress(b"\x00"+surfBuffer[i*scanlineSize:(i+1)*scanlineSize])
    
    chunkPayload += comp.flush()

    out += getPNGChunk(b"IDAT", chunkPayload)

    #IEND Chunk

    out += getPNGChunk(b"IEND", b"")

    return out

class Image(io.RawIOBase):

    """
    Represents an image. Wrapper around pygame.Surface
    This class contains a binary representation of an image and
    exposes methods to manipulate the graphical data.
    It can also be used as a file argument for discord.Client.send_file()
    """

    def __init__(self, width, height, name="untitled.png"):

        """
        Create a new Image.
        While the name argument doesn't serve any immediate purpose, it is useful to pass into client.send_message()
        as the filename. For this purpose, one should ensure to always end the name with ".png", otherwise
        Discords MediaProxy will get very confused and the image may not display correctly.
        """

        if not HAS_PYGAME:
            raise NotInitializedError("Can't create image: Library is not initialized.")

        self._display = _display
        #It is weird that this DOES take keyword arguments when convert() doesn't...
        #But that is just the way pygame works I guess
        self._surf = pygame.Surface((width, height), masks=BITMASKS)

        self._buffer = None
        self._offset = 0

        self.name = name #The .png is important here, MediaProxy is bad at guessing

    def setSurface(self, surf):

        """
        Update the internal surface to reference the object passed as surf.
        Users should not interface with this method directly, but instead use loadImage()
        or fromSurface().
        """

        self._surf = surf

    def getSurface(self):

        """
        Returns the internal surface of this image.
        """

        return self._surf

    def _createBuffer(self):

        """
        Internal method.
        Create a buffer object to read from containing the image data from the surface in a
        format understandable by discord.
        """

        return getPNGBuffer(self._surf)

    def read(self, n=0):

        """
        Returns data from the internal buffer, at most n bytes are returned. If n is less than one,
        this call will return an arbitrary amount of data.
        If the buffer is exhausted, this call will return an empty string.
        """

        if not self._buffer:
            self._buffer = self._createBuffer()
            self._offset = 0

        if len(self._buffer) <= self._offset:
            self._buffer = None
            self._offset = 0
            return b""

        if n < 1:
            n = len(self._buffer - self._offset)
        else:
            n = min(n, len(self._buffer))

        data = self._buffer[self._offset:self._offset+n]
        self._offset += n
        return data

    def _calculateLines(self, area, text, fontPath, startSize=20):

        """
        Internal method.

        This algorithm computes the larges font size,
        as well as the optimal line splitting for a given text and font face,
        such that it doesn't breach the specified areas borders.

        Returns a 2 element list, containing the font size, and a list of
        the lines.
        """

        size = startSize
        box = pygame.Rect(area)

        while True:
            font = pygame.font.Font(fontPath, size)
            words = text.split(" ")
            lines = []
            spaceWidth = font.size(" ")[0]
            totalHeight = 0
            while len(words) > 0:
                #we need to be careful here
                #if we don't read anything before going into the line splitting loop,
                #there is a possibility of the loop exiting on the first word due to it being too large for the line.
                #in this case, this becomes an infinite loop because no word is ever pulled from the queue.
                #To mitigate this, and to make sure lines are still split properly, we read the first word and also
                #set the starting width to its rendered size
                line = words.pop(0)
                lineWidth = font.size(line)[0]
                while len(words) > 0:
            
                    sizes = font.size(words[0])
                    #calculate new width of line by taking the accumulative line width plus the width of the current word and a separating space.
                    if lineWidth + spaceWidth + sizes[0] > box.width:
                        break

                    line += " " + words.pop(0)
                    lineWidth += spaceWidth + sizes[0]
                totalHeight += size
                #totalHeight += font.size(line)[1]

                lines.append([line, font.size(line)[0]])

            if totalHeight <= box.height:
                return [size, lines]
            size -= 1
            if size < 1:
                return [None, []]

    def writeText(self, area, text, color, font_name=None, shadow_color=(0, 0, 0), draw_shadows=False):

        """
        Write a text to the image.
        area should be a 4 value tuple or list containing x, y position and width and height of the text object.
        text should specify the text to be rendered, while color specifies the foreground color.
        font_name optionally specifies a font name to match for. The size will be chosen appropriately.
        If draw_shadows is True, this method will also draw a drop shadow below the text according to the
        set shadow_color.
        """

        HiSize = area[3]
        
        #TODO: May want to execute this call in a Thread, as it can be rather slow
        #(we're essentially using backtracking to find the right font size, and string
        #operations are expensive)
        fontPath = pygame.font.match_font(font_name) if font_name else None
        size, lines = self._calculateLines(area, text, fontPath, HiSize)
        font = pygame.font.Font(fontPath, size)

        shadow_size = int(max(1, size/20))

        for i in range(len(lines)):
            xoffset = area[2]//2-lines[i][1]//2
            if draw_shadows:

                s = font.render(lines[i][0], 1, shadow_color)
                #we have to increase the surface size to ensure there is enough space for the extrusion algorithm
                #to work properly
                s2 = pygame.Surface((s.get_width()+shadow_size*2, s.get_height()+shadow_size*2), pygame.SRCALPHA, masks=BITMASKS)
                s2.blit(s, (shadow_size, shadow_size))
                self._surf.blit(self._extrude(s2, shadow_size), [area[0]+xoffset-shadow_size, area[1]+i*size-shadow_size]) #recenter the shadow

            self._surf.blit(font.render(lines[i][0], 1, color), [area[0]+xoffset, area[1]+i*size])

    def _extrude(self, surf, width=1):

        """
        Extrude the objects in the surface by the specified width.
        This method examines each pixel in the image and copies it to
        the adjacent pixels in each dimension, if its color value is larger
        than the pixel it is copying to.
        This is particularly useful to draw drop shadows for objects such as
        text lines.
        The width argument specifies how many iterations are computed.
        """

        for i in range(width):

            surf.blit(surf, (0, 1), special_flags=pygame.BLEND_RGBA_MAX)
            surf.blit(surf, (0, -1), special_flags=pygame.BLEND_RGBA_MAX)
            surf.blit(surf, (1, 0), special_flags=pygame.BLEND_RGBA_MAX)
            surf.blit(surf, (-1, 0), special_flags=pygame.BLEND_RGBA_MAX)

        return surf

    @classmethod
    def fromSurface(cls, surf, name=""):

        """
        Construct a new Image from a pygame Surface
        """

        width = surf.get_width()
        height = surf.get_height()
        obj = Image.__new__(cls, width, height, name)
        obj.__init__(width, height, name)
        obj.setSurface(surf)
        return obj

    def resize(self, newWidth, newHeight, smooth=True):

        """
        Resize this image to the specified measurements.
        Will scale the image to fit new size if necessary.
        """

        if smoothscale:
            self._surf = pygame.transform.smoothscale(self._surf, (newWidth, newHeight))
        else:
            self._surf = pygame.transform.scale(self._surf, (newWidth, newHeight))

    def blit(self, source, dest=(0, 0), area=None, special_flags=0):

        """
        Blit the specified image on to this image.
        Supported source types are Image and pygame.Surface
        """

        if isinstance(source, Image):
            source = source.getSurface()
        elif not isinstance(source, pygame.Surface):
            raise TypeError("source must be either of type Image or pygame.Surface")

        self._surf.blit(source, dest, area, special_flags)

    def __str__(self):

        return "Image("+str(self._surf.get_width())+", "+str(self._surf.get_height())+")"

    def __bool__(self):

        #we consider the image having the boolean value true if its surface can be displayed
        return self._surf.get_width() > 0 and self._surf.get_height() > 0
