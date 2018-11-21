# Ram
ProtOS Discord Bot (Codename: Ram)

*Welp that deleted my old readme file, thanks a lot Git. Sheesh.*
Seriously there has to be a better way to merge a local repo onto the master without fucking everything up, even if their histories
don't match up. And there probably is. Remember to propose change to the Git devs to put a gigantic disclaimer text at the start of the
help command output describing how to do it.

I'm not going to send assassins or lawyers after you if you use any of this stuff. But I'm not going to give you permission either.
I'm not responsible for anything you do with any of this.

Mostly going to be using this repo for issue tracking, unsure as to how often I will update it. If Git lets me that is. If it requires me
to rewrite this stupid readme file each time I will just not bother.

Also loads of stuff is missing from this repo due to copyright reasons (like the conversation simulator or all of the content files) so
deal with that. I don't want to spend hours trying to deal with licenses. This is a private side project of mine and I cannot be bothered.
I like the GitHub interface so that's why this is on here. OMG VS, STOP PUTTING A ' AFTER ANY ' I WRITE, I DON'T WANT IT

Also testing some stuff since I have another project that may go open source at some point. So far I am disappointed.

#Installation
I have no idea, just go ahead and try. I use a different version of the program that has some additional modules and other files and never tested
if the repo actually works on its own. If it boots for you, great. If it doesn't, open an issue and I'll see if I can get around to actually testing
this crap.
Oh yeah, you'll probably have to do something about the conversation simulator, because that will definitely make it crash. Yep.

Dependencies:

	discord.py (duh; install the version with audio support, otherwise there may be issues. Refer to the discord.py repo for more information)
	youtube_dl (probably optional; may be required because I fucked up somewhere)
	soundcloud (optional; used for the music search engine)
	pygame (optional; used mostly for meme purposes)

All of the above modules can be installed using pip. I'm running my setup on Python 3.6 so you should probably do that as well.

Some important stuff to keep in mind if you DO want to try this: The bot will look for an xml document located at config/bot.xml . This document
should contain at least two things: Some sort of login information and your discord user ID, so that the bot can identify you in chat. The bot
accepts both bot tokens and username/password authentication, though a token is preferred, for reasons I will not elaborate on right now.
To input the token, create the following xml structure in bot.xml:

(fuck I hope this formatting does what I want it to)
```
<config version="2">
	<bot>
		<token>putYourTokenHere</token>
	</bot>
</config>
```

For the purpose of this document, I will from now on user a dotted format to describe config file entries. For example, the token tag we just created
will look like this in the new notation: bot.token = putYourTokenHere

If you want to use a normal user account, you can pass a username and password to the bot by adding the tags bot.username and bot.password respectively.
Be aware that bot.token will be used over username/password if both are specified.

Your user account ID should be added under the bot.owner tag; it can be obtained by rightclicking your name in discord with developer mode enabled.

[TODO: Write more information about configuring search engine tokens / twitch integration here]
[ALSO TODO: Make a wiki or something because this is getting quite long]

#Contributing
fix my markdown pls