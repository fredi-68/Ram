# The Command System Architecture
## API Tutorial And Reference

This folder contains all external bot commands.
These commands use a "plug and play like" system, meaning that they can be switched in and out without having to reconfigure the server - a simple reboot is enough. This is usefull for streamlining the command line interface towards certain use cases and helps to provide a simpler, cleaner command system.

This is also where you can put your own custom commands. Yes, that's right: Because of the aforementioned "plug and play" architechture, any valid python file containing a command conforming to the external command API (see cmdsys.py for more information) placed in this folder will be automatically imported and included in the command system for use from the command line or chat interface.

The package `cmdsys` defines and exposes the external command API, which is documented below.

### Introduction

This section describes the inner workings of the command system. You can skip it if you don't want to endure this short lesson in history relating to the development of this bot (which is totally understandable) but it does describe some interesting facts that may be relevant when developing new commands or especially, when debugging.

There was a time where every command was hardcoded into this bot. Yes, there were in fact endless amounts of if-elif-else clauses matching command patterns and parsing argument strings. Not only was this extremely uncomfortable to use, after I had implemented a few commands extending the list further got more and more complicated with the amount of code I had to sift through increasing ever so slightly.
As if that wasn't enough trouble already, almost every important command actually existed twice. YES, TWICE, IN THE SAME PROGRAM. You read correctly. This was because I had implemented the command line interface AFTER the first chat commands were already written and the new command line was, you guessed it, completely incompatible to the chat command interface. Instead of coming up with a better way to handle commands altogether, I decided to just implement every command twice - once for console and once for chat. This of course, while also being increadibly inefficient, caused the code to pile up twice as fast as well. On top of that, there was no guarantee that a command would be available on both interfaces. This was fine at first but when the time came to release version 2.0 I decided to put an end to this horror.
With version 2.0, the Unified Command System was introduced. This system had two purposes:

- Make developing new commands faster, safer and most importantly easier

- Provide ONE INTERFACE for both console and chat commands

This new interface worked great and commands could now be written using a simple object oriented development process which sped up production incredibly. However, there was still a problem: All commands were still located in the main file of the program, thus making said file incredibly hard to read or traverse. The obvious solution was to move every command to its own file, thus stripping the main file of about a third of its code. But a lot of the commands used references to objects in the global namespace. Dynamically adding all of those references to the command would be incredibly time consuming to do and it would also pose certain risks. Thus the command system was again separated. This time however, in INTERNAL and EXTERNAL commands.

- INTERNAL commands are commands that rely very heavily on system internal functionality that can't be easily replaced.
	These commands are hardcoded into the main program, thus having access to its global scope of variables and modules.
	They are also initialized a little bit differently (you don't have to worry about this)

- EXTERNAL commands are everything else. External commands provide a standardized API that abstracts most of the
    command handling from the user. There are basic ways of input/output, configuration and access to other APIs.

Internal commands are loaded on startup, regardless of user configuration. If there is an error in an internal command, the whole bot comes tumbling down and crashes with a nasty error message. External commands are more tolerant than that. Even if the file is not an actual command, it won't crash the bot - it will just ignore it. So feel free to experiment.

This worked well for a while. But with time the command parser grew out of control with more argument types being added and I eventually decided more abstraction was necessary. When I began
development on version 8, I thus decided to rewrite large portions of the software. The changes were so numerous in fact that I also decided to rewrite this documentation as well as translate
everything else to markdown.

So here we are.

### BEFORE YOU START


Before starting work on custom commands, there are some things you may want to take care of first.

If you are doing any sort of development, you should enable debug logging on console. Not only will this log every tiny bit of information you DON'T need, but also provide detailed logging while commands
are being loaded and executed during the initialization phase. You can activate debug logging by changing the level of the console handler in `config/logging.json`. If you're willing to put the time in,
you can also set levels manually for all the different loggers (can be useful, especially if you just want those netcode messages to disappear). If you need more information or more time to read it,
everything is always written to the log file.

To get error logs and tracebacks delivered straight through Discord, you can enable command debugging in the bot config by setting the text of the `config/bot/debug/showCommandErrors` tag to `1`.
Since this is a nonstandard configuration entry you may have to create the tag first.
Now any time a command fails to execute properly, you will receive a message with a traceback. This can help immensely, since the console log can advance very fast, especially in debug mode and error messages or tracebacks can be hard to read in time.

You will also want to familiarize yourself with the discord.py API, since a lot of the datatypes cmdsys uses are part of the library. There are also some things cmdsys cannot do, in which case
discord.py usually has your back. The client instance is exposed through an attribute as well as the original message. More on this later.

**NEW IN VERSION 4.6+**
If you are running the newest version, you don't have to reboot the bot to apply changes made to your commands code. Simply change your source code and then run the `+reloadCommands` command.
This will reload all external commands, including any changes made to the source file. This is usually much faster than restarting the bot completely. Note that if you are using code that is located in
other modules or packages and this code was modified, you may still have to reboot the bot in order for your changes to take effect.

### Command System API Tutorial



#### The Command Structure

Clearly the most interesting part of this whole thing since if you do this wrong your command won't be imported.

To write a module that contains a command you will need access to at least the `cmdsys.Command` class.
The easiest way to accomplish this is by calling

```python
from cmdsys import *
```


at the start of your module. This will also import all other classes and functions you will need later.

A command is defined by subclassing the Command class:

```python
class MyCommand(Command):

    pass
```

And we're done! You could put this file into the commands folder and the program would import your command and add it to the list.
The name of the class has no further significance. You can even put multiple commands in the same file.
But if you expected a new command called "MyCommand" to magically show up in the command list you will be surprised:
There is not such command in the list.
This is because we haven't actually configured our command yet.

#### The setup() Method & Command Attributes

To do this, we override the method Command.setup:

```python
class MyCommand(Command):

    def setup(self):

        self.name = "coolCommand"
        self.aliases.append("coolCmd")
        self.desc = "A cool command."
```

As you can see, we have supplied the command system with some additional information about our command. Let's walk you through the different attributes showcased here:

- name -    obvious naming is obvious: This attribute sets the name of the command. And not some internal name at
    that. This is the default name used to refer to the command in the command interface. This means, you 
	can invoke this command by typing `+[name]` in chat or `[name]` on console, with `[name]` being the name 
	field we just defined.

- aliases - This attribute contains a list of other names the command may be referred to as. For example, we
    could call the command we made just now by typing `+coolCommand` OR `+coolCmd` in the chat: The
    behaviour will be exactly the same, although the actual name is the preferred way of referencing
    the command.

- desc - 	This attribute provides some space for you to tell your users what your command is actually supposed
    to accomplish. A good name for a command is already descriptive enough so that idealy no further
	explanation is needed as to its functionality but it is always nice to describe a command in more
	detail. This is also the place to put information or disclaimers about possible arguments (we'll
	get to those later).

Now we've made a command that we can even call from the chat using our own command name but it doesn't actually do anything yet... let's change that!

#### The call() Method & Basic I/O

Add the following method to your class to add some actual functionality:

```python
class MyCommand(Command):

    def setup(self):

        self.name = "coolCommand"
        self.aliases.append("coolCmd")
        self.desc = "A cool command."

    async def call(self):

        await self.respond("Hello World!")
```

**HINT:** If you don't know what those *"async"* and *"await"* directives are about, you should read the asyncio documentation and the python tutorials on asynchroneous programming. Basic knowledge of this is required to write commands (or at least understand what you're doing).

That's it, we've written our hello world program. Tricked you into it mate. Oh well, gotta stay within the conventions.

Now let's go over which part does what.
The call method is a callback coroutine that gets called by the command handler every time the command is invoked by the user. It's signature is actually very similar to the command itself. It takes one positional argument, which is the command instance. Additionally, the command handler may pass additional keyword arguments holding the values passed in by the user as arguments on the command interface. More on this later.
For now, let's look at the call inside the method. We call the self.respond method, which is a coroutine. This is how we interact with the user. We get our input from our arguments as defined and send our output with the Command.respond method. This method actually does quite a few things and if you read the introduction you'll know that it has to translate between different systems dynamically. But we don't have to deal with any of that, just passing a string as the first argument will do the right thing. There is one more convenience functionality included with Command.respond: By specifying a second argument you can control an optional mention to be sent with your message. This will only work if the command was issued through chat:

- `await self.respond("Hi there")` will result in the bot sending a message saying "Hi there" to the channel where the command was issued.
- `await self.respond("Hi there",True)` will do the same but it will prepend the user mention of the command author, which will look like this: "*@username*, Hi there"

This is nice because it gives you the option of integrating mention support without having to figure out where the message was sent from first.

#### A Quick Example & Environment Atrributes

So now we have the tools to do basic input and output. But most of the time, the command needs to SOMEHOW access the environment the command was issued in. Let's take, for example, a command that lists all online members of a server (bad idea, since for large servers this would result in quite a large list but for our example this will have to do). To accomplish this, we will need access to the following variables:

- we need to know which server the command was issued from
- we need to query that server for a list of all online members

Arguments won't help us here so we need to get the server instance from somewhere else. The way this is done in cmdsys is via context variables and environment attributes.
There are several such attributes:

- environment.client
- environment.database
- environment.config
- environment.audio
- environment.conversation_simulator
- environment.voice_receive
- environment.cidsl

- Command.msg
- Command.response_manager

For our purpose of creating a member list command, we need access to the server the message was sent from. Luckily, `Command.msg` contains a reference to that very server. We just have to look up `Command.msg.server.members` to get a list of all members (or all online members if the member count is above 100).

So the code for our example command could look like this:

```python
class MyCommand(Command):

    def setup(self):

        self.name = "listUsers"
        self.desc = "This command lists all users that are online on this server."

    async def call(self, **kwargs):

        for member in tuple(self.msg.server.members):
            await self.respond(member.name)
```

It is worth noting that this would be an incredibly inefficient use of our I/O ressources. Every time the `Command.respond()` method is called, the message is sent to Discord via `Client.send_message()` **immediately, without buffering**. This means for a long list like this, you will be sending potentially hundreds of messages... and there is not doubt that Discord won't like that very much. A smarter idea would be to buffer our responses. Incidentally, the `respond()` method takes an additional optional parameter called flush_chat, which is True by default. By setting this to False, we can tell the ResponseManager to buffer our messages until we call `respond()` with `flush_chat=True`, or call `Command.flush()` respectively.
The message buffering system is even smart enough to automatically handle character limits for you. If you try to send a message longer than 2000 characters, the ResponseManager will try to break that message up into smaller pieces, as long as it can find a place to do so. Breakpoints for messages include newlines and new messages.
The ResponseManager will automatically flush our message buffer if we forget to do so, however, *when* this is going to happen is up to garbage collection, so it is best to always call `flush()` at the end of your command if you use manual message buffering.

So now we've discussed all major parts of our command system: Input, output and retrieving context information...
Wait a second, we never actually discussed how to get customized input using arguments right? Let's get to that as well before I forget again...

#### Arguments

Arguments are a very powerfull tool of cmdsys, because they allow you to customize your user interaction in a number of ways. The most basic way to add an Argument would be to do something like this:

```python
class MyCommand(Command):

    def setup(self):

        self.name = "echo"
        self.addArgument(StringArgument("message", True))
```

And that is it! A possible call method could look like this:

```python
    async def call(self, message="", **kwargs):

        if not message:
            await self.respond("You didn't say anything :(")
        else:
            await self.respond(message)
```

This command would take a single optional argument (meaning that it can be ommitted) and prints the content of that argument into the chat. Let's take a closer look at the constructor call of Argument. The first argument is the Argument name. This name is shown to the user in the command usage and help context and this is also the name of the keyword argument you will receive in the call method containing the argument the user entered. 
The second argument determines, if the Argument is optional or not. An optional Argument is NOT GUARANTEED to be included in the keyword argument list when call is... well.. called. This means your code has to account for this by, for example, specifying a default value for optional arguments or implement the necessary error handling. Take your pick.

Arguments are parsed, checked and converted automatically. There is, however, some special behaviour with Argument parsing one should be aware of. I will try to list all of those features here.

- Arguments are passed as keyword only arguments to your call method. The command system makes no effort to check your
	method signature before calling, which can result in some nasty errors if too many arguments were passed (which can
	happen if you add an Argument in the setup method but forget to add it to call as well). This is why you see the
	`**kwargs` starred expression at the end of each call method signature in the examples; it is there to prevent excess
	arguments from crashing the command. The command parser will never pass more arguments in than you specified, so if you
	write your commands properly there should be no need for this precaution.

- There is actually no such thing as *too many arguments* in cmdsys. Any excess arguments are merged and passed
	together with the last argument as a single value.

- Argument strings are split using `shlex.split()`. If you want to find out more about how an input string is split into arguments please refer to the functions documentation.

- As of CPython 3.6, the default dict implementation preserves argument passing order in keyword argument dicts. This means that kwargs will have all arguments in the same order they were
	defined in inside the setup() method. HOWEVER, one should not rely on this feature since the underlying implementation may change or be completely different on Python environments other
	than CPython, and this application will make no efforts in guaranteeing a certain order of arguments in the dict.

#### Conclusion

With that we have reached the end of our documentation for the command system used in the *ProtOS Discord Bot*. You now know how to create a command from scratch, configure it, add functionality, provide interaction with the user and his/her environment and customize the interface to suit your needs.

There is still a lot more of the API that is exposed by `cmdsys` and also by the accompanying modules `config.py`, `chatutils.py` and `ProtOS_Bot.py` . You can read through those files yourself to figure out how to use the more advanced API features but this tutorial should get you off to a good start with writing your own command extensions for this bot. Don't forget: Behind the structural requirements and the specialized APIs, command files are still normal python modules which means you can define additional data structures, classes, funtions and variables. Think of the setup method as your programs main entrypoint and the call method as your event handler. With that you can extend the basic command system to interact with your own code, other libraries or even other services running on the machine or the internet.

If you still get stuck with something you can always check the commands I supplied with the bot. There are a bunch in the command folder already and you can examine or copy code to create new commands or figure out what is wrong with one you have already made. I didn't implement the API for fun after all, most if not all of the functions are used somewhere in those modules. So go ahead and have a look!

### Command System API Reference


#### Databases And Data Persistence

With version 3.3, I introduced a new data persistency model using sqlite3: The DatabaseManager.
For the first time this enabled easy access to a context-sensitive, persistant, relational object storage system usable by command extensions.
However, as time went on the shortcomings of this first design became apparent. Thus, when version 8 came around, I decided to throw in a new
database system with the rest of the refactors.

First question you **should** have is "why should I use this instead of the configManager to store information?" *Good question. Here's why*:

- The `configManager` was originally designed to store information that is relevant for the bot itself and is *required* for it to function properly. However,
	 due to lack of a better alternative, any data that was *produced* by the bot at runtime was also stored in said config, which made it quite convoluted and hard to read.
	 Thus, with the introduction of the `DatabaseManager`, all configuration data should be stored using the configManager and all dynamically generated data should be
	 organized using the `DatabaseManager` instead.

- The DatabaseManager was designed to handle large, organized datasets. It is running on a fast and reliable sqlite3 backend and provides automatic caching and
	 structuring of data over multiple servers. Thus, your applications don't have to worry about *different servers* anymore, since each server is assigned its own
	 separate database.

- The configManager required the ENTIRE FILE to be rewritten to disk each time a part of the config was modified. On top of that, it was prone to security risks and
	 possible data corruption during saving. With the DatabaseManager, users can rely on sqlite3 to deal with these issues and just store and retrieve data like they
	 expect to.

With all of this mess out of the way, here is how you access the database using the Command System API:

The new database system introduced with version 8 is an *Object Relational Model* (or ORM for short). This means that the underlying relational database layout is wrapped
in an object oriented packaging, using `Model` classes instead of tables to interact with the data. Instead of writing query statements manually you construct them
programatically by chaining filters together that alter the data returned when the query is executed. Finally, you can read and write data on the model instances like
you would expect from an object oriented framework. Meanwhile the complexity of dealing with server specific databases, tables and even different database engines and
SQL dialects is entirely abstracted away by the framework. All you have to do is write your models and interfacing code.

Now for a quick introduction:

In order to create a new model, simply create a subclass of `database.Model` and define some fields:

```python
from database import Model, TextField, IntegerField, PKConstraint, AIConstraint

class Car(Model):

    car_model = TextField()
    horsepower = IntegerField()
    serial_number = IntegerField(constraints=[PKConstraint(), AIConstraint()])
```

And that's it! As usual, we will go over all the elements one by one.

- First, we create a subclass of `Model`. The name of the class will be used as the name for the table by default. Normally, you should not have to care about this.
- Second, we define some fields. Fields are the ORM equivalent of database columns. Each field has a name and a type - and a number of optional constraints.
	Once again, the ORM will use the name of your field class attribute as the name for the column. The actual datatype used depends on the database engine.
	Some datatypes expect you to provide additional parameters, refer to the inline documentation of those fields in this case.
- serial_number defines some additional constraints. In particular, we are looking at a `PKConstraint` and `AIConstraint` instance. These correspond to the
	`PRIMARY KEY` and `AUTO INCREMENT` parameters and tell the database engine that we want to explicitly declare our own primary key. If you would like to declare
	a composite primary key you may do so by applying the `PKConstraint` to multiple columns. Note that the ORM handles certain constraints automatically for you.
	For example, each field is not nullable by default. In order to enable null values, pass `null=True` as an argument to the fields constructor.
	Also note that not all constraints are supported by all database engines.
- Something you cannot see in this example is the ORM's implicit primary key feature. To ensure functionality on backends which do not offer implicit keying on
	their own, the ORM will automatically create an integer primary key and link it to your model in case you do not specify an explicit primary key yourself.
	This field is called `id` by default. If you want a custom primary key you should declare it as such.

Now that we have our model we need to tell the database system to create a table for it. There are two ways to do this. You may either:

1. call `DatabaseManager.register_model(model_class)` OR
2. call `DatabaseEngine.register(model_class)` directly.

What's the difference? To understand this, we need to understand the purpose of the `DatabaseManager` and `DatabaseEngine` classes.
The engine is responsible for communicating with the database. As such, it represents exactly **one** database connection. The manager meanwhile handles all communication
between the application and the database layer. It creates and caches database connections on the fly whenever such a connection is requested.
Which method you want to use depends on the situation. `DatabaseManager.register_model()` will register your model on **every database** requested from this point forward.
In many cases this is not what you want. It may be a better idea to call `DatabaseEngine.register()` instead, since this will only affect the currently active database.
However, if you choose this method, you will have to make sure to call it **every time** you want to access the database with this model. In general, calling
`DatabaseManager.register_model()` is safe if you are relying on the ORM's guild multiplexing features. If you are using the global or any other custom database, using
`DatabaseEngine.register()` may be the better choice.

Now that we have created our model on the database, we can use the ORM to execute queries against this model.
To access the database, you must first tell the `DatabaseManager` which database you are interested in. The database manager usually lives in environment.database, a name
automatically imported by `from cmdsys import *`. In most cases, you want the database that corresponds to the current message context, i.e. the guild the command was
sent in. Because this is such a common operation, it has its own method: `environment.database.get_db_by_message(msg)`.
If you want a different database instead, you can use `environment.database.get_db(id)` instead.
Regardless which method you choose, you will end up with a `DatabaseEngine` instance. This is your main entrypoint to the database system.

First, let's look into how we can construct a new instance of our model. While you may be inclined to simply call the models constructor directly (and this is most
certainly possible), this is not the intended way of going about it. Instead, call `DatabaseEngine.new(model_class)`. This will create and return a new instance of your
model, as well as execute any pre-creation hooks the engine has attached to this method.

The returned object will be an unbound model instance. This means you cannot perform certain operations on it (such as deleting it, which doesn't make sense on a
model which doesn't exist yet). You can however begin to set the models fields. To do this, simply assign values to the instance attributes. They will be automatically
cached in the background. No database operations are performed at all until you call `Model.save()`. This will instruct the `DatabaseEngine` to create a record of your
model in the database. Prior to the actual database operation a number of validators will be run on your model to ensure the values you entered are valid and within
acceptable ranges. Some field types will also apply code injection protection at this stage. Once the operation completes, your models data will be bound - meaning it
represents a live record on the database. You may now delete it with `Model.delete()` or apply further changes and update it by calling `save()` again.

To query the database for a list of models, you can call `DatabaseEngine.query(model_class)`. This will return a `Query` object linked to the `DatabaseEngine` as well as
your `Model` class. The `Query` class is a container implementing several accessor methods to enable you to perform operations on the records it contains. Note that the
moment you use any of these interfaces for the first time, the `Query` is implicitly executed. A query string is constructed in the background and run on the database table,
then the result is returned, converted back into `Model` instances and exposed through the `Query` instance. Since this is a bit more complicated than creating new instances,
I will provide a short example.

Let's assume we have registered our *Car* model on the database. Now we want to search for any cars that match the serial number 1234.

```python
for car in database.query(Car).filter(serial_number=1234):
    print(car.car_model, car.horsepower)
```

Wait, what just happened?

- We first construct a `Query` with `database.query(model_class)`. The `Query` object doesn't actually appear anywhere in the statement though - it is implicitly converted
	to an iterator which we immediately use in a for loop to iterate over the `Model` instances returned.
- The `Query.filter()` call tells our `Query` instance that we want to restrict the query to only those instances that have a *serial_number* of *1234*. The `filter()` method
	can accept any `Filter` instance as long as it is supported by the database engine. In this example we used the `Equals` filter, however, because its use is so
	common there is a shorthand for it - simply specify the attribute value as a keyword argument. A call to `filter()` always returns the `Query` instance. This allows you
	to chain multiple filters together effortlessly. Using this syntax, any database query can be written as a single line of code!

And that is pretty much it! There is one more thing I would like to mention however.
When you want to delete a large amount of records, it is easy to just construct a query, then iterate over it, deleting every record by itself.
This has several performance implications. For one, each model instance is implicitly created by the database engine on query execution, which costs time and memory.
Secondly, a seperate query has to be created and executed for each deleted record. This is very time consuming due to the overhead between Python and the database backend.
Most database backends support deleting multiple records at the same time. To facilitate this, a `Query` instance offers a delete() method, similarly to `Model.delete()`.
This will delete **all** records that match the queries filter spec. The best part about it is that in most situations the records in question do not even have to be accessed.
If your chosen database engine adapter does not support bulk deletion this is no problem either. `Query` will automatically fall back on the iterative deletion algorithm
described in the beginning in these cases. Thus you should always use `Query.delete()` when deleting multiple records at once.


##### FAQ


-	Q: Where are the logfiles?
	A: All SQL statements are logged during execution, so check the logfiles if anything weird is going on.

-	Q: I want to close the database connection. How do I do this correctly?
	A: The `DatabaseManager` does not expose a clean up method to close open databases.
	This is intended and one should **never** attempt to explicitly close a database connection.
	To ensure efficient data access and support a heavily asynchroneous program the `DatabaseManager` caches connected databases automatically.
	In case of system failure, any connections are implicitly closed and any uncommitted changes will be dropped.
	To ensure data consistency, it is sufficient to commit all changes made to the database before your command/application shuts down.

-	Q: Are database connections thread safe?
	A: The `DatabaseManager` and all related systems are **NOT THREAD SAFE!!!** You should thus avoid interacting with the database outside of the main thread.
	If you absolutely need to, consider setting up a server using asyncios integrated features to handle database access for your application.

-	Q: I would like to use a different database engine than *SQLite3*. Is this possible?
	A: Absolutely! However, currently only *SQLite3* is supported out of the box. You can however write your own database adapter by subclassing `DatabaseEngine`.
	You then need to pass this class to the `DatabaseManager` cosntructor. This happens in the constructor of the bot client itself.

-	Q: Is there support for custom datatypes?
	A: Yes, by subclassing `Field` you can implement custom datatypes. Each field has a `typeref` parameter which determines the datatype used to serialize
	the data in the database. Which data conversion and validation mechanisms you implement on top of that is up to you.

-	Q: Is there support for transactions?
	A: Use `DatabaseEngine.transaction()` to obtain a `Transaction` object. This object acts as a context manager. Use it as follows:

    ```python
    with database.transaction() as t:
        # ... perform some database operations ...
    # transaction is implicitly closed and all changes are commited at once.
    ```

	If an exception occurs within the transaction block, the transaction is rolled back automatically.

-	Q: Is there support for foreign key fields?
	A: At the moment the ORM does not support foreign key relationships or table joins. These features are planned for a later release.

#### Clean Up

So, imagine the following scenario:

Your command enables users to query some information from a remote website and posts it into the chat. Because this command produces quite a lot of output you have it set up where any messages that are posted by it are autodeleted after a minute.
Now a bot administrator decides to conduct maintenance on the bot and shuts it down temporarily. There is, however, still a message in chat that will only be deleted in about 20 seconds. Luckily, you thought of that (well done) and set up a clean up handler in the destructor of your command that would delete all messages currently still being displayed if the object was GCed. Unfortunately, as your admin attempts to shut down the bot, it crashes with a nasty error message and the messages are still in the chat. What happened?

Implementing a clean up handler in a destructor doesn't always have the desired effect. This practice will create a race condition between the command and the discord client being GCed. If the discord client shuts down before the clean up method gets executed, deleting messages will obviously not work. How can we deal with this issue?

Since I had a similar problem while implementing the timeout command, I decided to introduce a clean up method registration function. To register a coroutine to be executed at bot shutdown, call

```python
cmdsys.cleanUpRegister(coro)
```

This will schedule coro to be run BEFORE the client terminates, guaranteeing that you will have full access to all features of the command system.
You may specify additional positional or keyword arguments. The coroutine will be called with these arguments in order of input.

All clean up methods will be executed FIFO. However, there is no guarantee that clean up methods registered by different commands will always be executed in the same order as well. **YOU SHOULD NOT RELY ON THIS**. If your clean up handler is state dependend, consider to store all relevant information inside your command instance.
There is currently no guarantee that clean up handlers will be executed if the bot crashed. In fairness, the APIs may not be available in this scenario anyways.

#### Dynamic Image Creation And Manipulation

Again, imagine the following scenario:

Your command displays some information to the user. However, this information is very convoluted, complex or has properties that otherwise make it difficult to understand, especially in text form. You've considered using an embed to somewhat structure it better but this is still not what you wanted. If only there was a way of getting full control over the way discord displayed your message...

If you've read this far and now expect me to reveal that you can in fact gain complete control of the client UI, I'll have to disappoint you. However, what you COULD do is render the information as an image dynamically and then upload that as a file to discord. This is what this part of the documentation focuses on.

To dynamically create and manipulate images there are a couple of libraries that do a good job. There is, however, already a wrapper library included with the command system. It operates on the pygame multimedia/game development package that itself is a wrapper around the SDL multimedia library. To load and manipulate images using this wrapper you don't have to actually know how pygame or SDL work, but you will have to have the package installed. Since this is an optional module in the ProtOS Discord Bot distribution, its features may or may not be available to you depending on the platform/runtime environment. **ALWAYS CHECK THE AVAILABILITY OF THE IMAGE MANIPULATION MODULES BEFORE YOU USE THEM OR YOUR CODE CAN CRASH AT RUNTIME**.

To get access to the convenience functions, import the imagelib module. It is safe to do this regardless of package availability.
Before you can access any functions or classes in this module, you will have to call its `init()` function. This function will set up the modules components and initialize the pygame backend. If you are running pygame as a part of your main application (for example as part of another command) be aware that this call will reset the display mode so you may need to execute it in a different process.
If the `init()` call succeeds, all functions and classes in the imagelib module are now available.
To load an image, call `imagelib.loadImage(path)`. Available file formats depend on the platform, but PNG and JPEG are usually supported. imagelib works with per pixel alpha by default so PNG alpha channels will be respected and converted correctly.
The `imagelib.loadImage()` function returns a new `Image` object. To manipulate the pygame surface directly, call `Image.getSurface()`. You should not attempt to manually alter the pixel format (depth or masks) since it could break the `Image` instance. Use of the `Image.setSurface()` method is thus discouraged. If you just want to put some text on an image, you can use `Image.writeText()` which abstracts most of the text render handling away from the user.
The Image class exposes a number of methods that mimic the behaviour of the `pygame.Surface` class, however, if you need more specific control over the surfaces or plan to use imagelib together with another library, you can set `Image` surfaces yourself. Just remember that you should always call `imagelib.convert()` on your surfaces before this, it will make sure that your surfaces have the correct pixel format.

To send the image off to discord you don't need to do anything, just pass the Image object to `client.send_file()` as the fp argument. imagelib will automatically convert your image into a PNG bytestream and send it to discord. To make it show up correctly, you should also specify a filename that ends with .png.

#### Logging

If you want to log information as your command is doing its thing, there is a logger attached to each command available through `Command.logger`. Its name is automatically set to the commands name. This works for those cases where all you want is to display progress information on the console so you can tell what your command is doing during development. However, if you want to log a message to a specific channel each time a command is executed; don't worry, we got a system for that.
The coroutine `Command.log` posts a message in all configured audit log channels. The bot has commands for managing audit log channels from the Discord client. The nice thing about this is that you don't have to worry about setting up channel IDs or something similar. You can just use Command.log and it will work - on every server and every platform, as long as at least one logging channel is configured for a server. If there is no such channel, the call does nothing.
However, to keep the spam down you should limit logging to security relevant information only. What does that mean exactly? Basically any action that has an impact on one or multiple members experience. This includes things like timeouts, kicks, bans, changing role permissions, etc. Discord provides its own audit log by default, though you cannot write to it directly. Think of this feature as an expandable alternative to that system. Try to view your command from an administrators perspective: What would you want to see, what would you consider unimportant?

#### Audio

If you want to use Discords voice chat to play back some audio you can still use the discord.py backend to create and play back an audio stream using the provided API.
However, doing so may interfere with other features of the bot also using the audio system, since only one audio source may ever be registered on the discord.py audio backend
at any given time.
To get around this, it is encouraged to use the integrated ProtOS Discord Bot Audio Subsystem, which is located at audio.py
This API uses an object oriented design, focusing on different audio source types, which may be played back or queued on a channel. All the complicated work of managing the queue
and mixing different sounds is abstracted away from the user for greater convenience.

To use this API you will need to subclass audio.Sound, or use one of the provided classes. There are subclasses for creating FFMPEG streams or even downloading web resources completely
automatic. The Sound API is described in more detail in the inline documentation of the `audio.py` module.

To queue a sound, you may use the Command.playSound method. Note that this is not a coroutine, however, the call is still non-blocking since the sound playback will be managed in a
different thread from the main application.
The `Command.playSound` method takes three arguments: An `audio.Sound` instance representing the sound you wish to play, a channel instance of the voice channel you want the sound to be
played on and a boolean specifying whether or not this sound should be played back synchronously or asynchronously.
An asynchronous sound will be played by the audio system as soon as it becomes available, where as a synchronous sound will only start playback once the channel is free. Synchronous
sounds are best used for audio that has a long duration or is meant to be played as part of a sequence. Asynchronous sounds are best used where response time matters.
Synchronous sounds will be placed in a queue before their playback has started, which can be inspected by users using the +queue command.
Since Asynchronous sounds never enter the queue, they are also not affected by advanced features such as looping/repeat modes.

Note that if the bot is currently not connected to the voice channel you are requesting playback for, the call will fail with an exception. This is intended as it prevents sounds
queued to different channels from interrupting playback and the bot moving between channels frequently.