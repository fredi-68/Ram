#Discord ProtOS Bot
#
#Author: fredi_68
#
#Config manager, data persistence

from xml.etree import ElementTree as ET #we use etree xml documents to store config information...
import sqlite3 as sql #...and sqlite3 for data persistence
import weakref
import logging
import shutil
import os
from typing import List, Union
from pathlib import Path

import discord

DEFAULT_CONFIG_PATH = "config/bot.xml"
DEFAULT_DATABASE_PATH = "config/db"

class VersionError(Exception):

    """
    This exception is thrown if the config file version doesn't match the version specified by the application.
    """

    pass

class ConfigManager():

    """
    This class represents an xml configuration file.
    It functions similar to an xml DOM, but exposes different methods to manipulate the data fields directly
    using paths instead of nested elements.

    You can still interact with the DOM by using the xElement methods.
    If you prefer to interact with the values directly, use the xElementText methods instead.
    Always refer to the method documentation as the exact purpose isn't always immediately obvious.
    """

    logger = logging.getLogger("ConfigManager")

    def __init__(self, path=DEFAULT_CONFIG_PATH, requireVersion=None):

        """
        Initialize config manager.
        Optional path argument specifies path to load config from.
        Optional requireVersion argument specifies a minimum version the application requires.
        """

        self.minVersion = requireVersion
        self.path = path
        self.version = "N/A"
        self.load()

    def load(self, path=None) -> bool:

        """
        Load a config from <path> or the default config.
        """

        if path:
            self.path = path

        self.logger.info("Loading configuration file...")
        try:
            self.root = ET.ElementTree(file=self.path).getroot() #Load the config (extracting the root element from the element tree generated from a file)
        except OSError:
            self.logger.error("Failed to load config data: File could not be opened.")
            return False
        except ET.ParseError:
            self.logger.error("Failed to load config data: An error occured while parsing XML data.")
            return False
        except:
            self.logger.error("Failed to load config data: An unknown error occured.")
            return False

        self.version = self.root.get("version","N/A")
        try:
            v = int(self.version)
            if self.minVersion and v < self.minVersion: #tell the user something is wrong with the config and also why we crashed
                raise VersionError("Version number doesn't meet application requirements! (minimum version "+str(self.minVersion)+"/config version "+self.version+")")
        except: #either the version attribute wasn't found, which means the config is REALLY old or it was manipulated. In both cases, having a minimum version requirement makes this config invalid.
            if self.minVersion:
                raise VersionError("Version number doesn't meet application requirements! Config is very old or was manipulated.")
        
        self.logger.info("Config data loaded. (Configuration file version "+self.version+")")

        return True

    def save(self, path=None) -> bool:
        
        """
        Saves the entire config tree to the disk.
        This will override any config file present at the time of saving. Set <path> to save to a different location.
        """

        if path:
            self.path = path
        
        self.logger.info("Saving config...")

        try:
            ET.ElementTree(self.root).write(self.path)
        except OSError:
            self.logger.error("Failed to save config data: File could not be saved.")
            return False
        except:
            self.logger.error("Failed to save config data: An unknown error occured.")
            return False

        return True

    def getElement(self, path=None, create=False) -> ET.Element:

        """
        Get element at <path>. If path is None returns root element.
        Optional <create> argument specifies if the path to the element should be created if it doesn't exist.
        """

        if not path: return self.root

        pElements = path.split(".") #We access elements using a class path like format
        cElement = self.root
        for i in pElements:
            try:
                cElement = cElement.find(i)
            except:
                if create:
                    nElement = ET.Element(i) #create element if it doesn't exist
                    cElement.append(nElement)
                    cElement = nElement
                else:
                    return None

        return cElement

    def getElementText(self, path=None, default="", create=False) -> str:

        """
        Shorthand for getElement(path).text . Supports default values.
        Optional <create> argument specifies if the path to the element should be created if it doesn't exist.
        """

        element = self.getElement(path,create=create)
        if element == None:
            return default
        return element.text

    def getElementInt(self, path=None, default=0, create=False) -> int:

        """
        Shorthand for int(getElement(path).text) . Supports default values and automatic type checking.
        Optional <create> argument specifies if the path to the element should be created if it doesn't exist.
        """

        element = self.getElement(path, create=create)
        if element == None:
            return default
        try: #try to convert value to an integer, if this fails return the default
            return int(element.text)
        except:
            return default

    def addElement(self, path: str, element: ET.Element) -> ET.Element:

        """
        Add the element to the config at <path>. Returns the modified parent element.

        WARNING: the element will be inserted into the element in path. All parent elements will be created if they don't exist.
        Thus path is NOT the path to <element> but the path to the element containing <element>.

        WARNING: This doesn't immediately save the document to prevent bottlenecks in case multiple add operations are required to be executed after another.
        If you are passing critical data you should call the save() method after you are done to prevent data loss.
        The bot will autosave the config every 5 minutes.
        """

        if not isinstance(element, ET.Element):
            raise ValueError("element must be of type xml.etree.ElementTree.Element!")

        pElements = path.split(".") #We access elements using a class path like format
        cElement = self.root
        for i in pElements:
            try:
                cElement = cElement.find(i)
            except:
                nElement = ET.Element(i) #create element if it doesn't exist
                cElement.append(nElement)
                cElement = nElement
        cElement.append(element)
        return cElement

    def setElement(self, path: str, element: ET.Element) -> ET.Element:

        """
        Set the element in the config at <path>. Returns the modified parent element.

        WARNING: If the parent element of <element> contains multiple elements with the same tag as <element>, ALL OF THEM WILL BE DELETED IN THE PROCESS OF THIS CALL.
        If this is not what you want, use addElement() instead.

        WARNING: This doesn't immediately save the document to prevent bottlenecks in case multiple set operations are required to be executed after another.
        If you are passing critical data you should call the save() method after you are done to prevent data loss.
        The bot will autosave the config every 5 minutes.
        """

        if not isinstance(element, ET.Element):
            raise ValueError("element must be of type xml.etree.ElementTree.Element!")

        pElements = path.split(".")[:-1] #We access elements using a class path like format (except the last one since we want to remove and then readd it)
        cElement = self.root
        for i in pElements:
            try:
                cElement = cElement.find(i)
            except:
                nElement = ET.Element(i) #create element if it doesn't exist
                cElement.append(nElement)
                cElement = nElement
        for i in list(cElement.findall(path.rsplit(".", 1)[1])):
            cElement.remove(i) #remove all elements with matching tag name from the parent element
        cElement.append(element) #re-add our new element
        return cElement

    def setElementText(self, path: str, text: str) -> ET.Element:

        """
        Set the element text in the config at <path>. Returns the modified parent element.

        WARNING: If the parent element of <element> contains multiple elements with the same tag as <element>, ALL OF THEM WILL BE DELETED IN THE PROCESS OF THIS CALL.
        If this is not what you want, use addElement() instead.

        WARNING: This doesn't immediately save the document to prevent bottlenecks in case multiple set operations are required to be executed after another.
        If you are passing critical data you should call the save() method after you are done to prevent data loss.
        The bot will autosave the config every 5 minutes.
        """

        e = ET.Element(path.rsplit(".", 1)[1])
        e.text = text
        return self.setElement(path, e)

    def removeElement(self, element: ET.Element):

        """
        Remove the element from the config. Element must be an element in the config data tree for this to work.

        WARNING: This doesn't immediately save the document to prevent bottlenecks in case multiple remove operations are required to be executed after another.
        If you are passing critical data you should call the save() method after you are done to prevent data loss.
        The bot will autosave the config every 5 minutes.
        """

        self.root.remove(element) #dunno if this works, we'll see

    def removeElementsByTag(self, path: str, tag: str) -> ET.Element:

        """
        Removes all subelements from the element at <path> that match <tag>. This will fail silently if there are no elements present. Returns a list of the elements removed.

        WARNING: This doesn't immediately save the document to prevent bottlenecks in case multiple remove operations are required to be executed after another.
        If you are passing critical data you should call the save() method after you are done to prevent data loss.
        The bot will autosave the config every 5 minutes.
        """

        pElements = path.split(".")[:] #We access elements using a class path like format
        cElement = self.root
        for i in pElements:
            try:
                cElement = cElement.find(i)
            except:
                nElement = ET.Element(i) #create element if it doesn't exist
                cElement.append(nElement)
                cElement = nElement
        rElements = list(cElement.findall(tag)) #make a list of elements to be removed
        for i in rElements:
            cElement.remove(i)
        return rElements