# vim: sts=4:sw=4:et:tw=80:nosta
import asyncio, aiohttp, config, json, logging, random, websockets
from datetime import datetime

class HitboxClient:

    """Handles connections to Hitbox WS Chat."""

    def __init__(self, channel, nick=None, logintoken=None):
        """Creates a new Hitbox Client.
            :nick: The user's Hitbox nickname (default None)

        """

        self._nick = nick
        self._logintoken = logintoken
        self._server = None
        self._token = None
        self._channel = channel
        self._loggedIn = False
        self._namecolor = "D44F38"
        self._waitingmessages = []
        self._dispatcher = asyncio.Semaphore(value=0)
        self._log = logging.getLogger("ws")

    @asyncio.coroutine
    def get_servers(self):
        """Obtain the WS server list from Hitbox.
            :returns: The array of available servers.

        """

        r = yield from aiohttp.request("GET",
            "{}/chat/servers".format(config.API_URL))

        if r.status >= 400:
            raise IOError(r.status)
        d = yield from r.read()

        try:
            j = json.loads(d.decode())
        except ValueError:
            r.close()
            return None

        r.close()
        return j

    @asyncio.coroutine
    def select_server(self, list=None):
        """Obtain a random server from the server list.
            :list: List of servers to select from (default None)
            :returns: A string containing a Hitbox WS server.

        If list is None, obtain from get_servers()

        """

        if list == None:
            list = yield from self.get_servers()
        self._server = random.choice(list)['server_ip']
        return self._server

    @asyncio.coroutine
    def get_token(self):
        """Obtain a token from the selected server.
            :returns: The WebSocket ID from the selected server.

        """

        r = yield from aiohttp.request("GET",
            "http://{}/socket.io/1/".format(self._server))
        d = yield from r.read()
        d = d.decode("UTF-8").split(":")[0]
        self._token = d

        r.close()
        return d

    @asyncio.coroutine
    def establish_connection(self):
        """Connect to a Hitbox chat server.
            :returns: The websocket used to connect

        """

        yield from self.select_server()
        yield from self.get_token()
        self._socket = yield from websockets.connect(
            "ws://{}/socket.io/1/websocket/{}".format(
                self._server, self._token))

        return self._socket

    @asyncio.coroutine
    def close_connection(self):
        """Disconnect from the Hitbox chat server.
            :returns: True on success, False on error

        """

        try:
            yield from self.partChannel()
            yield from self._socket.close()
            return True
        except:
            return False

    @asyncio.coroutine
    def connect(self):
        """Connect to a chat server and receive incoming messages."""
        yield from self.establish_connection()
        yield from self.recv()

    @asyncio.coroutine
    def recv(self):
        """Get incoming messages as they come in.  Runs until stopped."""
        while True:
            try:
                msg = yield from self._socket.recv()
            except websockets.exceptions.ConnectionClosed:
                self._log.debug("Connection closed.  No longer receiving " +
                    "incoming messages.")
                break
            self._log.debug("< {}".format(msg))

            if msg == "1::" and not self._loggedIn:
                self._log.debug("Logging into channel #{}..." \
                    .format(self._channel))
                yield from self.joinChannel()
            elif msg == "2::":
                self._log.debug("PING? PONG!")
                yield from self.pong()
            else:
                json = msg[4:]
                yield from self.dispatchMessage(json)

    @asyncio.coroutine
    def send(self, msg):
        """Send messages to the Hitbox chat server."""
        yield from self._socket.send(msg)
        self._log.debug("> {}".format(msg))

    @asyncio.coroutine
    def getNextMessage(self):
        """Grabs the next incoming message and sends it to the object using the
        socket.  Blocks if a message is not available."""
        yield from self._dispatcher.acquire()
        return self._waitingmessages.pop(0)

    @asyncio.coroutine
    def dispatchMessage(self, msg):
        """Adds a message to the message queue and signals that a message is
        available, unblocking anything calling getNextMessage()"""
        self._waitingmessages.append(msg)
        self._dispatcher.release()
        self._log.debug("Message dispatched.  Sem: {}" \
            .format(repr(self._dispatcher)))

    @asyncio.coroutine
    def joinChannel(self):
        """Joins the channel this socket is assigned to."""
        prefix = "5:::"
        if self._nick == None:
            nick = "UnknownSoldier"
        else:
            nick = self._nick
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "joinChannel",
                    "params": {
                        "channel": self._channel,
                        "name": nick,
                        "token": self._logintoken,
                        "isAdmin": False
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def partChannel(self):
        """Logs out of the channel.  This should be called before closing the
        socket."""
        prefix = "5:::"
        if self._nick == None:
            nick = "UnknownSoldier"
        else:
            nick = self._nick
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "partChannel",
                    "params": {
                        "name": nick
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def pong(self):
        """Responds to server pings with an identical message."""
        yield from self.send("2::")

    @asyncio.coroutine
    def userList(self):
        """Requests the user list from a channel."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "getChannelUserList",
                    "params": {
                        "channel": self._channel
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def userInfo(self, nick):
        """Get information about a user including it's roles.
            :nick: Nick to get information about
        
        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "getChannelUser",
                    "params": {
                        "channel": self._channel,
                        "name": nick
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def getChatColors(self):
        """Get valid chat colors you can use."""
        r = yield from aiohttp.request("GET",
            "{}/chat/colors".format(config.API_URL))
        d = yield from r.read()
        j = json.loads(d)

    @asyncio.coroutine
    def timeout(self, nick, time=300):
        """Timeout (ban temporarily) a user from a channel for a specified
        amount of seconds.
            :nick: Target nickname
            :time: Number of seconds to ban

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "kickUser",
                    "params": {
                        "channel": self._channel,
                        "name": nick,
                        "token": self._logintoken,
                        "timeout": time
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def ban(self, nick):
        """Indefinitely ban a user from a channel.
            :nick: Target nickname

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "banUser",
                    "params": {
                        "channel": self._channel,
                        "name": nick
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def ipban(self, nick):
        """Bans a user by IP.  Be careful with IP bans as a single IP can be
        dealt to a pool of users (e.g. Universities, Offices, ...)
            :nick: Target nickname

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "banUser",
                    "params": {
                        "channel": self._channel,
                        "name": nick,
                        "token": self._logintoken,
                        "banIP": True
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def unban(self, nick):
        """Removes a ban on the specified nick.
            :nick: Target nickname

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "unbanUser",
                    "params": {
                        "channel": self._channel,
                        "name": nick,
                        "token": self._logintoken
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def addMod(self, nick):
        """Grants the specified nick moderation permissions.  You must be the
        channel admin.
            :nick: Target nickname

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "makeMod",
                    "params": {
                        "channel": self._channel,
                        "name": nick,
                        "token": self._logintoken
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def removeMod(self, nick):
        """Remove moderation permissions from the specified nick.  You must be
        the channel owner.
            :nick: Target nickname

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "removeMod",
                    "params": {
                        "channel": self._channel,
                        "name": nick,
                        "token": self._logintoken
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def setSlow(self, time=0):
        """Restrict users to sending only one message every specified number of
        seconds.
            :time: Number of seconds to delay

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "slowMode",
                    "params": {
                        "channel": self._channel,
                        "time": time
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def enableSubOnly(self):
        """Restrict chatting to channel subscribers.  Moderators and higher may
        still chat."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "slowMode",
                    "params": {
                        "channel": self._channel,
                        "subscriber": True,
                        "rate": 0
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def disableSubOnly(self):
        """Lift the restriction on chatting and allow everyone to talk."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "slowMode",
                    "params": {
                        "channel": self._channel,
                        "subscriber": False,
                        "rate": 0
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def sendMessage(self, text):
        """Send a message to the current channel.  Will be rejected if slow mode
        or subscriber mode is preventing you from talking.
            :text: Text to send.  Limited to 300 characters

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "chatMsg",
                    "params": {
                        "channel": self._channel,
                        "name": self._nick,
                        "nameColor": self._namecolor,
                        "text": text
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def sendDM(self, nick, text):
        """Send a direct message to another Hitbox user.  Can be rejected if the
        user is not accepting direct messages.
            :nick: Target nickname
            :text: Text to send

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "directMsg",
                    "params": {
                        "channel": self._channel,
                        "from": self._nick,
                        "to": nick,
                        "nameColor": self._namecolor,
                        "text": text
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def setSticky(self, msg=""):
        """Set a sticky message to the given message.
            :msg: Message to stick.  Omit to remove

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "motdMsg",
                    "params": {
                        "channel": self._channel,
                        "name": self._nick,
                        "nameColor": self._namecolor,
                        "text": msg,
                        "time": self.get_timestamp()
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def startPoll(self, question, choices, subscribersOnly, followersOnly):
        """Begin a poll with the given options.
            :question: Question to ask
            :choices: Array of answers
            :subscribersOnly: Boolean indicating whether subscribers only can
                vote.  Overrides followersOnly
            :followersOnly: Boolean indicating whether followers only can vote

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "createPoll",
                    "params": {
                        "channel": self._channel,
                        "question": question,
                        "choices": choices,
                        "subscribersOnly": subscribersOnly,
                        "followersOnly": followersOnly,
                        "start_time": self.get_timestamp(),
                        "nameColor": self._namecolor
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def pollVote(self, choice):
        """Vote on an active poll.
            :choice: Integer indicating vote.  Starts at 0

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "voteMsg",
                    "params": {
                        "name": self._nick,
                        "channel": self._channel,
                        "choice": choice,
                        "token": self._logintoken
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def pausePoll(self):
        """Pause the active poll."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "pausePoll",
                    "params": {
                        "channel": self._channel,
                        "token": self._logintoken
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def restartPoll(self):
        """Restart the active poll."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "startPoll",
                    "params": {
                        "channel": self._channel,
                        "token": self._logintoken
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def endPoll(self):
        """End the active poll.  Once you end a poll, you cannot restart it -
        you must create a new poll."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "endPoll",
                    "params": {
                        "channel": self._channel,
                        "token": self._logintoken
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def createRaffle(self, question, prize, choices, subscribersOnly, followersOnly):
        """Create a giveaway.  Same as creating a poll, except with a prize.
            :question: Question to ask
            :prize: Prize to win
            :choices: Array of choices to pick from
            :subscribersOnly: Whether to limit to subscribers
            :followersOnly: Whether to limit to followers

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "createRaffle",
                    "params": {
                        "channel": self._channel,
                        "question": question,
                        "prize": prize,
                        "choices": choices,
                        "subscribersOnly": subscribersOnly,
                        "followersOnly": followersOnly,
                        "start_time": self.get_timestamp(),
                        "nameColor": self._namecolor
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def pauseRaffle(self):
        """Pauses the active giveaway."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "pauseRaffle",
                    "params": {
                        "channel": self._channel
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def endRaffle(self):
        """Ends the active giveaway.  You must be in this state in order to pick
        a winner."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "endRaffle",
                    "params": {
                        "channel": self._channel
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def restartRaffle(self):
        """Resumes the giveaway if it is in a paused state."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "startRaffle",
                    "params": {
                        "channel": self._channel
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def raffleVote(self, choice):
        """Vote in a giveaway with the given choice.
            :choice: Integer indicating choice (starts at 0)

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "voteRaffle",
                    "params": {
                        "name": self._nick,
                        "channel": self._channel,
                        "choice": choice
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def pickRaffleWinner(self, choice):
        """Pick a winner, from those who picked the given choice.
            :choice: Winning choice

        """
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "winnerRaffle",
                    "params": {
                        "channel": self._channel,
                        "answer": choice
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def hideRaffle(self):
        """Hides the raffle from the UI."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "hideRaffle",
                    "params": {
                        "channel": self._channel
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    @asyncio.coroutine
    def cleanupRaffle(self):
        """Clears the giveaway after ending it and picking the winner."""
        prefix = "5:::"
        j = json.dumps({
            "name": "message",
            "args": [
                {
                    "method": "cleanupRaffle",
                    "params": {
                        "channel": self._channel
                    }
                }
            ]
        })
        yield from self.send(prefix + j)

    def get_timestamp(self):
        """Obtains the current timestamp in the format that the Hitbox API needs
        it in."""
        return datetime.datetime.now() \
            .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
