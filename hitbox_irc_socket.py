# vim: sts=4:sw=4:et:tw=80:nosta
import asyncio, aiohttp, json, random, websockets
from datetime import datetime

class config:
    API_URL = "https://api.hitbox.tv"

class HitboxClient(asyncio.Protocol):

    """Handles connections to Hitbox WS Chat."""

    def __init__(self, channel, nick=None, logintoken=None):
        """Creates a new Hitbox Client.
            :nick: The user's Hitbox nickname (default None)

        """

        asyncio.Protocol.__init__(self)

        self._nick = nick
        self._logintoken = logintoken
        self._server = None
        self._token = None
        self._channel = channel
        self._loggedIn = False
        self._namecolor = "D44F38"

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
            :returns: TODO

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
        yield from self.establish_connection()
        yield from self.recv()

    @asyncio.coroutine
    def recv(self):
        while True:
            msg = yield from self._socket.recv()
            print("< {}".format(msg))

            if msg == "1::" and not self._loggedIn:
                print("Logging into channel #{}...".format(self._channel))
                yield from self.joinChannel()
            elif msg == "2::":
                print("PING? PONG!")
                yield from self.pong()

    @asyncio.coroutine
    def send(self, msg):
        yield from self._socket.send(msg)
        print("> {}".format(msg))

    @asyncio.coroutine
    def joinChannel(self):
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
        yield from self.send("2::")

    @asyncio.coroutine
    def userList(self):
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
        r = yield from aiohttp.request("GET",
            "{}/chat/colors".format(config.API_URL))
        d = yield from r.read()
        j = json.loads(d)

    @asyncio.coroutine
    def timeout(self, nick, time=300):
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
        return datetime.datetime.now() \
            .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

@asyncio.coroutine
def main_client():
    hs = HitboxClient(channel="esi")
    yield from hs.connect()

loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(main_client())
finally:
    loop.close()
