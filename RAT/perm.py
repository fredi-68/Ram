
import sqlite3 as sql

class User():

    def __init__(self, name, key, pStatus, pRun, pChangeState, pUpdate, pPerms):

        """
        Create a new user account object.
        Users shouldn't instanciate this class directly but instead use the
        respective methods of a DatabaseHandle instance.
        """

        self.name = name
        self.key = key
        self.permissions = {
            "viewStatus": pStatus,
            "runCommands": pRun,
            "runRATCommands": pChangeState,
            "update": pUpdate,
            "editPermissions": pPerms
            }

    def checkPermissions(self, permissions=[]):

        """
        Checks if this user has the given set of permissions.
        Returns True on success, False on failure
        """

        for i in permissions:
            if not self.permissions[i]:
                return False
        return True

    def checkKey(self, key):

        """
        Checks if the given key matches the users authentication key.
        Returns True on success, False on failure
        """

        return key == self.key

    def _serialize(self):

        """
        Returns the internal representation of the user account
        """

        return (self.name,
                self.key,
                self.permissions["viewStatus"],
                self.permissions["runCommands"],
                self.permissions["runRATCommands"],
                self.permissions["update"],
                self.permissions["editPermissions"]
                )

class DatabaseHandle():

    def __init__(self, path="users.db"):

        self._database = sql.Connection(path)
        self._cursor = self._database.cursor()
        self._setUpTables()

    def _setUpTables(self):

        self._cursor.execute("CREATE TABLE IF NOT EXISTS users (name text, key blob, pStatus integer, pRun integer, pChangeState integer, pUpdate integer, pPerms integer)")

        self._database.commit()

    def createUser(self, name, key):

        """
        Registers a new user in the database.
        Name and key are the username and password with which to login to the remote control client.
        Returns the new user on success, False on failure
        """

        if self.getUser(name):
            return False #user already exists
        newuser = User(name, key, 0, 0, 0, 0, 0) #create user
        self._cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", newuser._serialize()) #save new user
        self._database.commit() #save changes to database
        return newuser

    def deleteUser(self, user):

        """
        Deletes a user from the database.
        The user must exist and may not be the last remaining user with administrative access (all permissions).
        Returns True on success, False on failure
        """

        if not self.getUser(user.name):
            return False #user doesn't exist
        if self._is_last_admin(user):
            return False
        self._cursor.execute("DELETE FROM users WHERE name=:name", {"name": user.name}) #delete user
        self._database.commit() #save changes to database

        return True

    def _is_last_admin(self, user):

        """
        Internal method.
        Checks if the given user is the last remaining admin.
        """

        allusers = self.getAllUsers()
        for i in allusers:
            if all(list(i.permissions.values())):
                if i.name == user.name:
                    continue #this is the user being checked so he doesn't count
                return False #found another admin

        #no admin in the userbase, check the user for admin permissions
        if all(list(user.permissions.values())):
            return True
        return False #This is weird, there is not a single admin in the database... 

    def setUser(self, user):

        """
        Copies the given user into the database.
        The user must exist and any new permission set may not remove the last
        remaining user with administrative access (all permissions).
        Returns the user on success for efficient call chaining or False on failure
        """

        #check if user exists (we also need this record for further processing)
        olduser = self.getUser(user.name)
        if not olduser:
            return False #User doesn't exist
        if self._is_last_admin(olduser) and user.permissions.values() != olduser.permissions.values(): #User is trying to change permissions of last remaining administrator, which is not permitted
            return False

        #User exists and new user is valid. Update the database
        updatelist = list(user._serialize()[1:])
        updatelist.append(user.name) #switch position of username to last
        self._cursor.execute("UPDATE users SET key=?, pStatus=?, pRun=?, pChangeState=?, pUpdate=?, pPerms=? WHERE name=?", updatelist) #update like creation but with name last instead of first
        self._database.commit() #save the changes

        return user

    def setPermission(self, user, permissions={}):

        """
        Sets the permissions for the given user.
        The user must exist and the new permission set may not remove the last
        remaining user with administrative access (all permissions).
        Returns the modified user instance with the new permission set or False on failure
        """

        user.permissions.update(permissions) #change permissions of the user
        return self.setUser(user) #write to db

    def getUser(self, name):

        """
        Queries for the user with the given name.
        The name must be the name of an existing user.
        Returns a user instance representing the user account or False on failure
        """

        try:
            self._cursor.execute("SELECT * FROM users WHERE name=:name",{"name": name})
        except:
            return False

        result = self._cursor.fetchone()
        if not result:
            return False

        return User(*result)

    def getAllUsers(self):

        """
        Queries for all users currently registered in the database.
        Returns a list of User instances representing user accounts. The list may be empty
        """

        self._cursor.execute("SELECT * FROM users")
        userlist = []
        for user in self._cursor.fetchall():
            userlist.append(User(*user))

        return userlist
