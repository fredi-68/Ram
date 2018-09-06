#Discord ProtOS Bot
#
#Author: Jascha "fredi_68" Hirsekorn
#
#Config manager, data persistence

from xml.etree import ElementTree as ET #we use etree xml documents to store config information...
import sqlite3 as sql #...and sqlite3 for data persistence
import weakref
import logging
import shutil
import os

import discord

DEFAULT_CONFIG_PATH = "config/bot.xml"
DEFAULT_DATABASE_PATH = "config/db"

class VersionError(Exception):

    """
    This exception is thrown if the config file version doesn't match the version specified by the application.
    """

    pass

class configManager():

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

    def load(self, path=None):

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

    def save(self, path=None):
        
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

    def getElement(self, path=None, create=False):

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

    def getElementText(self, path=None, default="", create=False):

        """
        Shorthand for getElement(path).text . Supports default values.
        Optional <create> argument specifies if the path to the element should be created if it doesn't exist.
        """

        element = self.getElement(path,create=create)
        if element == None:
            return default
        return element.text

    def getElementInt(self, path=None, default=0, create=False):

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

    def addElement(self, path, element):

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

    def setElement(self, path, element):

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

    def setElementText(self, path, text):

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

    def removeElement(self, element):

        """
        Remove the element from the config. Element must be an element in the config data tree for this to work.

        WARNING: This doesn't immediately save the document to prevent bottlenecks in case multiple remove operations are required to be executed after another.
        If you are passing critical data you should call the save() method after you are done to prevent data loss.
        The bot will autosave the config every 5 minutes.
        """

        self.root.remove(element) #dunno if this works, we'll see

    def removeElementsByTag(self, path, tag):

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

class DatasetHandle():

    logger = logging.getLogger("Database")

    def __init__(self, database, table, index, columns):

        """
        This class represents a set of data. This data is generally arbitrary, but limited by the table and the DatabaseHandle being used.
        One DatasetHandle instance can contain multiple SQL statements that will be treated as one compount statement. Thus, it can be used to
        efficiently handle multiple database entries and methods are provided for working on multiple entries at once without having to worry
        about the individual statements.
        
        This class should NOT be instanciated directly, but ONLY through DatabaseHandle.createDataset()

        To manage multiple datasets at once, use the Transaction class.
        """

        #Internal values
        self._database = database
        self._table = table
        self._columns = columns
        self._index = index

        self.defaultValues()

    def defaultValues(self):

        """
        Reset the internal data storage to the default values.
        WARNING: This will override any changes you may have made to the data.
        """

        self._entries = [0]*len(self._columns) #set up our internal data storage
        for i in self._columns:
            self.setValue(i[1], None)

    def getColumnNames(self) -> list:

        """
        Returns a list of all column names in this dataset
        """

        columns = []
        for i in self._columns:
            columns.append(i[1])

        return columns

    def hasColumn(self, column) -> bool:

        """
        Returns true if this dataset contains a column with the specified name, false otherwise
        """

        for i in self._columns:
            if i[1] == column:
                return True

        return False

    def getIndex(self) -> int:

        """
        Returns the index of the entry this dataset represents
        """

        return self._index

    def getColumnIndex(self, column) -> int:

        """
        Returns the index of the given column name.
        """

        for i in self._columns:
            if i[1] == column:
                return i[0]

        raise KeyError("No such column.")

    def _convertValue(self, type, value) -> object:

        """
        Internal method.
        Force converts the given argument into the correct database representation.
        This method also checks for invalid argument formatting and possible exploits.
        Errors that occur while converting types will not be suppressed.
        """

        if type in ("text"):
            retValue = str(value)
            if ";" in retValue:
                raise ValueError("Unexpected symbol ';' in value of type str.") #This is a common SQL injection technique
            return retValue
        elif type in ("int"):
            if value == None:
                return 0
            return int(value)
        elif type in ("real"):
            if value == None:
                return 0.0
            return float(value)
        elif type in (""):
            return None
        else:
            raise ValueError("Unexpected type for value, must be valid sqlite3 datatype.")

    def setValue(self, column, value):

        """
        Set the value of the specified column to the specified value.
        Passing None as the value will reset the column to its default value.
        If column is a string, it will be interpreted as the name of the column.
        If it is an integer, it will be interpreted as the index of the column, starting at 0.
        WARNING: The index will be calculated based on the columns visible to this dataset. If for some reason this dataset was
        initialized using partial column data, the index may have an unexpected offset. It is recommended to use named identifiers
        to refer to columns.
        """

        if isinstance(column, str):
            column = self.getColumnIndex(column)

        elif isinstance(column, int):
            pass

        else:
            raise ValueError("column must be of type str or int")

        self._entries[column] = self._convertValue(self._columns[column][2], value)

    def setAllValues(self, values):

        """
        Set all values of the dataset at once.
        This method excpects that values is a list of the exact length of the column amount.
        """

        for i in range(0, len(values)):
            self._entries[i] = values[i]

    def getValue(self, column) -> object:

        """
        Get the value of the specified column. If column is a string, it will be interpreted as the name of the column.
        If it is an integer, it will be interpreted as the index of the column, starting at 0.
        WARNING: The index will be calculated based on the columns visible to this dataset. If for some reason this dataset was
        initialized using partial column data, the index may have an unexpected offset. It is recommended to use named identifiers
        to refer to columns.
        """
        
        if isinstance(column, str):
            column = self.getColumnIndex(column)

        elif isinstance(column, int):
            pass

        else:
            raise ValueError("column must be of type str or int")

        return self._entries[column]

    def add(self):

        """
        Add this dataset to the database.
        """

        self._database.addDataset(self)

    def delete(self):

        """
        Delete this dataset from the database. It must be part of the database.
        """

        self._database.deleteDataset(self)

    def update(self):

        """
        Write changes made to this dataset to the database.
        If the dataset doesn't exist in the database yet, it will be created.
        """

        if not self.exists(): #dataset isn't actually in the database yet, so we need to execute and INSERT statement isntead of an UPDATE statement
            return self.add()

        self._database.updateDataset(self)

    def getTable(self) -> str:

        """
        Returns the table name
        """

        return self._table

    def getDatabase(self) -> object:

        """
        Returns the database instance this dataset is tied to
        """

        return self._database

    def searchDatabaset(self, query={}):

        """
        This method will search the database using query as a set of requirements to be met.
        It should be a dictionary using column names as keys and the respective values as values of the dict.
        This dataset will automatically be updated to reflect the results.
        WARNING: Changes you made to this dataset MAY be lost.
        """

        self._database.searchDataset(self, query)

    def exists(self) -> bool:

        """
        Returns True if this dataset exists in the database, False if not
        """

        return self._index > -1

    def __eq__(self, other):

        #To be equal, the other object has to be a dataset...
        if not isinstance(other, self.__class__):
            return False

        #...index the same table...
        if not self.getTable() == other.getTable():
            return False

        #...Have access to the same columns...
        l = set(self.getColumnNames()) #use sets for efficiency
        l.union(other.getColumnNames())
        for i in l:
            if not (self.hasColumn(i) and other.hasColumn(i)):
                return False

            #...and have the same values
            if not (self.getValue(i) == other.getValue(i)):
                return False

        return True

class Transaction():

    """
    Represents a compound view on a database table.
    Wraps multiple datasets and allows various operations to be performed on them.

    All operations are virtual, in that they don't alter the database at all (like the dataset operations).
    To commit changes they need to be written to the DatabaseHandle (for example by calling the Transaction.update() method).

    One major point of this class is that the statements performed on all datasets are commited as one transaction.
    This is intended to abstract transaction management away from the user by allowing arbitrary datasets to be chained
    together, manipulated together and then updated together with automatic rollbacks in case of failure.

    This class supports basic set theoretic operations and inline notation using Pythons magic methods.
    The supported operations are:

        -Union (|)
        -Intersection (&)
        -Difference (-)
        -Symmetric difference / xor (^)
    """

    def __init__(self, database, datasets=[]):

        """
        Create a new Transaction instance.

        Database is the DatabaseHandle used as the source of the datasets.

        If datasets is specified it should be a list, iterator or generator (something that implements the
        iterator/generator protocol) that produces a sequence of datasets. Valid are all datasets that meet
        the requirements specified in Transaction.addDataset()
        """

        self._database = database
        self._datasets = list(datasets)

    def getDatasets(self):

        """
        Return the internal list of datasets that make up this Transaction.
        The list cannot be used to modify the query as it is a copy.
        """

        return self._datasets.copy()

    def update(self):

        """
        Updates all datasets in this Transaction, writes and commits all changes to the database.
        """

        pass

    def addDataset(self, dataset):

        """
        Add a new dataset to this Transaction.
        It doesn't matter if the dataset exists or not; the Transaction will automatically
        figure out how to handle updates.

        The only requirement for datasets in a Transaction is that they all share the same Database.
        They may be part of different tables.

        A dataset may not be added more than once.
        """

        if not isinstance(dataset, self.__class__):
            raise TypeError("dataset must be of type DatasetHandle")

        if dataset in self._datasets:
            raise ValueError("dataset is already part of this Transaction")

        self._datasets.append(dataset)
        return True

    def removeDataset(self, dataset):

        """
        Remove a dataset from this Transaction.
        The dataset must be part of the dataset.
        """

        if not dataset in self._datasets:
            raise ValueError("can't remove dataset from Transaction since it isn't a part of it.")

        self._datasets.remove(dataset)
        return True

    def search(self, table, req={}):

        """
        Search the specified table of the database for datasets that meet the requirements.

        THIS WILL OVERRIDE THE CONTENTS OF THIS TRANSACTION.
        To combine two search results use Transaction.union(), Transaction.intersect(), Transaction.diff() or Transaction.xor()
        """

        pass

    def union(self, other):

        """
        Computes the unity of this Transaction and another Transaction object.
        """

        if not isinstance(other, self.__class__):
            raise TypeError("Can only compute union of two Transaction objects")

        for i in other:
            if not i in self:
                self.addDataset(i)

    def intersect(self, other):

        """
        Computes the intersection of this Transaction and another Transaction object.
        """

        if not isinstance(other, self.__class__):
            raise TypeError("Can only compute intersection of two Transaction objects")

        for i in self:
            if not i in other:
                self.removeDataset(i)

    def diff(self, other):

        """
        Computes the difference of this Transaction and another Transaction object.
        """

        if not isinstance(other, self.__class__):
            raise TypeError("Can only compute difference of two Transaction objects")

        for i in self:
            if i in other:
                self.removeDataset(i)

    def xor(self, other):

        """
        Computes the symmetric difference of this Transaction and another Transaction object.
        But symmetric difference is too long a term so this method is called xor() instead.
        There is an xor() alias named symmetricDifference() that does the same thing.
        """

        if not isinstance(other, self.__class__):
            raise TypeError("Can only compute symmetric difference of two Transaction objects")

        l = self.getDatasets()
        l.extend(other.getDatasets())

        for i in l:
            #if it is in both, delete it
            if (i in self) and (i in other):
                self.removeDataset(i)
            #if it is not in this one but in the other one, add it
            if (not i in self) and (i in other):
                self.addDataset(i)

    def symmetricDifference(self, other):

        """
        Computes the symmetric difference of this Transaction and another Transaction object.
        """

        return self.xor(other)

    #MAGIC METHOD COMPATABILITY

    def __len__(self):

        return len(self._datasets)

    def __iter__(self):

        return self._datasets.__iter__()

    def __repr__(self):
        
        return "Transaction("+repr(self._database)+")"

    def __str__(self):

        return "Transaction @ "+str(self._database)+" ("+str(len(self))+" element(s))"

    def __bool__(self):

        return len(self) > 0

    def __contains__(self, item):

        return item in self._datasets

    def __or__(self, other):

        return self.union(other)

    def __and__(self, other):

        return self.intersect(other)

    def __sub__(self, other):

        return self.diff(other)

    def __xor__(self, other):

        return self.xor(other)

class DatabaseHandle():

    logger = logging.getLogger("Database")

    def __init__(self, path, serverID):

        """
        This class represents one database reflecting stored information about a server.

        It exposes methods that manipulate the database directly, however, using these can be insecure, since no argument checking is done.
        It is better to use createDataset() to instanciate DatasetHandles and manipulate these instead. They provide a more streamlined interface
        for managing SQL statements and can even be grouped for better performance.
        """

        self.serverID = serverID

        self._db = sql.connect(path+".db")
        self._cursor = self._db.cursor()

        self._performSetup()

    #Internal methods

    def createTableIfNotExists(self, name, entries={}, autocommit=True):

        """
        Helper method for _performSetup.
        This method will create a table if there isn't one with the same name already.
        """

        vars = []
        for i in entries.items():
            vars.append((i[0]+" "+i[1]))

        self._execute("CREATE TABLE IF NOT EXISTS "+name+" ("+(", ".join(vars))+")")

        if autocommit:
            self._db.commit()

    def _execute(self, *args, **kwargs):

        """
        Wrapper around the cursor executor that logs every call to the SQL runtime
        """

        self.logger.debug("SQL execution called with parameters "+str(args)+", "+str(kwargs))
        self._cursor.execute(*args, **kwargs)

    def _performSetup(self):

        """
        This method will perform first time setup if the database just got created.
        """

        self.createTableIfNotExists("blockedUsers", {"userID":"text"}, False)
        self.createTableIfNotExists("blockedChannels", {"channelID":"text"}, False)
        self.createTableIfNotExists("pinChannels", {"channelID":"text"}, False)
        self.createTableIfNotExists("tasks", {"channelID":"text", "frequency":"int", "message":"text", "time":"text", "last":"text"}, False)
        self.createTableIfNotExists("auditLogChannels", {"channelID":"text"}, False)
        self.createTableIfNotExists("timeoutRole", {"roleID":"text"}, False)
        self.createTableIfNotExists("timeoutCount", {"userID":"text", "count":"int"}, False)

        self._db.commit()

    def _getFromTable(self, table, query, values=""):

        """
        Helper method.
        This method will execute a select call on the given table of the database
        using query as the select statement after WHERE.
        If values is given, it should specify the values to return, as a string.
        If ommited, it defaults to *
        """

        self._execute("SELECT " + (values if values else "*") + " FROM "+table+" WHERE ("+query+")")
        return self._cursor.fetchall()

    def _addToTable(self, table, entry, autocommit=True):

        """
        Helper method.
        This method will execute an insert call on the given table
        of the database using entry as the value list.
        """

        self._execute("INSERT INTO "+table+" VALUES "+entry)
        if autocommit:
            self._db.commit()

    def _deleteFromTable(self, table, query, autocommit=True):

        """
        Helper method.
        This method will execute a delete call on the given table of the database
        using query as the select statement after WHERE.
        """

        self._execute("DELETE FROM "+table+" WHERE "+query)
        if autocommit:
            self._db.commit()

    def _updateInTable(self, table, entry, query, autocommit=True):

        """
        Helper method.
        This method will execute an update call on the given table of the database
        using query as the select statement after WHERE and entry as the new set of values after SET.
        """

        self._execute("UPDATE "+table+" SET "+entry+" WHERE "+query)
        if autocommit:
            self._db.commit()

    def _getTableInfo(self, table):

        self._execute("PRAGMA table_info("+table+")") #returns a list of tuples like: (index, name, type, canBeNull, default(None=uninitialized), isPrimary)

        columns = self._cursor.fetchall()

        if not columns:
            #table doesn't exist in current database
            #TODO: How do we want to handle this? We could a) try to create the table (and dynamically add columns later) or b) just let the entire call fail.
            #For now, we will do the latter
            raise ValueError("Table "+str(table)+" doesn't exist in current database.")

        return columns

    def _getRowCount(self, table):

        """
        Determine the amount of rows in a given table
        """

        self._execute("SELECT COUNT(*) FROM "+table)

        return self._cursor.fetchall()[0][0] #we are looking for the first column in the first row

    def addDataset(self, dataset):

        """
        Add a dataset to the database.
        """

        self._execute("INSERT INTO "+dataset.getTable()+"("+", ".join(dataset.getColumnNames())+") VALUES ("+", ".join(map(str,dataset._entries))+")")
        self._db.commit()

    def deleteDataset(self, dataset):

        """
        Delete a dataset from the database. The dataset must exist in the database.
        """

        if not dataset.exists(): #dataset must exist
            return False

        self._deleteFromTable(dataset.getTable(), "ROWID like "+str(dataset.getIndex()), True) #delete dataset
        dataset._index = -1 #dataset doesn't exist anymore, ensure index reflects this

    def updateDataset(self, dataset):

        """
        Update a dataset in the database. The dataset must exist in the database.
        """

        pairs = []
        for i in dataset.getColumnNames():
            pairs.append(i+"="+str(dataset.getValue(i)))

        self._updateInTable(dataset.getTable(),", ".join(pairs),"ROWID IS "+str(dataset.getIndex()),True)

    def getDataset(self, dataset) -> DatasetHandle:

        """
        Get the dataset from in the database. Returns a dataset containing the retrieved information. It may be empty.
        THIS METHOD CURRENTLY DOES NOTHING. USE searchDataset INSTEAD!
        """

        #Dunno if I will actually ever use this method... leave it here for now, may remove it later
        pass

    def searchDataset(self, dataset, req={}):

        """
        Searches the database for a dataset that meets the specified requirements.
        Returns True if a matching data segment was found and the dataset was updated to reflect the new data.
        Returns False if there was no match and the dataset was not updated.
        """

        q = []
        for i in req.items(): #Create our query definitions
            q.append(i[0]+"="+i[1])

        res = self._getFromTable(dataset.getTable(), ",".join(q), "*, ROWID")

        if not res:
            return False #in case of faliure we don't update anything and just inform the user that things went sideways

        res = res[0] #take the first row out of the list

        #update the dataset
        dataset.setAllValues(res[:-1])
        dataset._index = res[-1:][0]

        return True

    def createDataset(self, table):

        """
        Create a new dataset using a table as a template. This dataset is NOT guaranteed to be part of the database.
        """

        columns = self._getTableInfo(str(table))

        return DatasetHandle(self, table, -1, columns) #The -1 here tells us that this dataset has not been assigned an index yet (is uninitialized)

    def createDatasetIfNotExists(self, table, req):

        """
        Convenience method.
        This method will search for a data segment that matches the given requirements.
        If no such dataset is found, a new one will be created instead.
        In any case, the user will get an initialized dataset to work with.
        If the dataset was created from nothing, its index will be -1
        """

        dataset = self.createDataset(table) #we create a new dataset
        for i in req.items():
            dataset.setValue(i[0], i[1])

        self.searchDataset(dataset, req) #we search for a matching data segment
        #If our search was successful, the dataset will be updated with the new values from the query result. If not, it will keep the values we set before

        return dataset

    def enumerateDatasets(self, table) -> list:

        """
        Enumerates all Datasets in a given table and returns a list of datasets. Each dataset is guaranteed to be part of the database. It may be empty.
        """

        self._execute("SELECT *, ROWID FROM "+table)
        queryResult = self._cursor.fetchall()
        if not queryResult:
            return []
        retList = []
        self.logger.info(str(queryResult))
        for i in queryResult: #create DatasetHandles for all rows of data
            ds = self.createDataset(table)
            ds.setAllValues(i[:-1])
            ds._index = i[-1]
            retList.append(ds)
        return retList

    def __del__(self):

        #close database connections to avoid data corruption
        self._cursor.close()
        self._db.close()

class DatabaseManager():

    logger = logging.getLogger("Database")

    def __init__(self, path=DEFAULT_DATABASE_PATH):

        """
        This class manages database connections for all servers.
        DatabaseHandle instance should ONLY be created using this class,
        since it can use caching to ensure performance and security.
        """

        self.path = path
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True) #create database directory if it doesn't exist yet
        self._cache = weakref.WeakValueDictionary()

    def getServer(self, serverID):

        """
        Load the database for the specified server and return the DatabaseHandle.
        Will create database if it doesn't exist.
        """

        try: #perform cache lookup for this server
            ref = self._cache[serverID] 
            return ref
        except KeyError: #the object may have been garbage collected while we were referencing it, or just doesn't exist
            pass

        handle = DatabaseHandle(self.path+"/"+serverID, serverID)
        self._cache[serverID] = handle #cache our databaseHandle
        return handle

    def getDatabaseByMessage(self, msg=None):

        """
        Like getServer(), but accepts discord.Message objects instead of strings.
        This method will load and return the database corresponding to the server the message
        was posted in.
        If the message was posted in a private/group channel instead, or wasn't specified at all,
        this method will return the "global" database instead for convenience.
        """

        if isinstance(msg, discord.Message):

            if msg.server:
                return self.getServer(msg.server.id)

        elif msg != None:
            raise TypeError("msg must be of type discord.Message or None")

        #fall back to global database for DMs and unspecified messages
        return self.getServer("global")