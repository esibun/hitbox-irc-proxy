# vim: sts=4:sw=4:et:tw=80:nosta
import asyncio, aiohttp, json, random, websockets

class config:
    API_URL = "https://api.hitbox.tv"

class HitboxClient(asyncio.Protocol):

    """Handles connections to Hitbox WS Chat."""

    def __init__(self, channel, nick=None):
        """Creates a new Hitbox Client.
            :nick: The user's Hitbox nickname (default None)

        """

        asyncio.Protocol.__init__(self)

        self._nick = nick
        self._server = None
        self._token = None
        self._channel = channel

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
    def connect(self):
        """Connect to a Hitbox chat server.
            :returns: TODO

        """

        yield from self.select_server()
        yield from self.get_token()
        self._socket = yield from websockets.connect(
            "ws://{}/socket.io/1/websocket/{}".format(
                self._server, self._token))

        return self._socket
