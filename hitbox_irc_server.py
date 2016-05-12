# vim: sts=4:sw=4:et:tw=80:nosta
import asyncio, config, json, logging
import hitbox_get_user_token
from hitbox_irc_socket import HitboxClient

class IRCServerProtocol(asyncio.Protocol):

    """Handles incoming IRC connections and creates a Hitbox chat connection
    for each channel.  Each connection creates a new instance of this class, so
    you may allow multiple clients to connect.  However, keep in mind that there
    is a limit to the number of connections allowed to Hitbox chat per IP."""

    def __init__(self):
        """Creates a new IRC server."""
        asyncio.Protocol.__init__(self)

        self._log = logging.getLogger("irc")
        self._transport = None
        self._nick = None
        self._pass = None
        self._loggedin = False
        self._logintoken = None
        self._channels = {}

    def connection_made(self, transport):
        """Called by Protocol whenever a new connection is made to the IRC
        server.
            :transport: The transport to read and write from

        """
        peername = transport.get_extra_info("peername")
        self._log.info("Connection from {}".format(peername))
        self._transport = transport

    def data_received(self, data):
        """Called by Protocol whenever new data is available for the currrent
        connection.  The purpose of this class is prety much to parse a command,
        determine whether to call it synchronously or asynchronously, then call
        the appropriate function.
            :data: The data received from the client

        """
        msg = data.decode("UTF-8").split("\n")[:-1]
        for line in msg:
            # Some IRC clients also send \r with newlines - if this is the case,
            # we need to remove it.  For HexChat, this is the case, for mIRC this
            # is not the case.  (see #3)
            line = line.strip() #some IRC clients also send \r - remove this
            if line.split(" ")[0].strip().lower() != "pass":
                self._log.info("<< {}".format(line))
            else:
                self._log.info("<< PASS ***")
            tok = line.split(" ")
            cmd = tok[0].strip().lower()
            # We call the PASS, NICK, and USER commands synchronously to avoid
            # having to lock and wait for subsequent commands to finish.  This
            # also allows us to respond if, for instance, the PASS command was
            # not sent when the NICK and USER commands have been.
            if cmd in ["pass", "nick", "user"]: #Call these in sync
                func = getattr(self, "on_{}".format(cmd), None)
                if func != None:
                    self._log.debug("Calling on_{} (synchronously)".format(cmd))
                    func(tok[1:])
            else:
                func = getattr(self, "on_{}".format(cmd), None)
                if func != None:
                    self._log.debug("Calling on_{}".format(cmd))
                    asyncio.ensure_future(func(tok[1:]))
                else:
                    self._log.debug("Unknown command {}({})".format(cmd, tok[1:]))

    def on_pass(self, tok):
        """Called by data_received in response to a PASS command.
            :tok: An array of tokens parsed from the command

        """
        self._pass = tok[0]
        self._log.debug("Pass set to ***")

    def on_nick(self, tok):
        """Called by data_received in response to a NICK command.
            :tok: An array of tokens parsed from the command

        """
        self._nick = tok[0].strip()
        self._log.debug("Nick set to {}".format(self._nick))

    def on_user(self, tok):
        """Called by data_received in response to a USER command.  Will block if
        the nickname has not been set yet.  This command ignores all of the
        input past the command but handles all of the registration logic.
            :tok: An array of tokens parsed from the command
        """
        if self._loggedin == False:
            if self._pass != None and self._nick != None:
                self._log.debug("Logging in user {}".format(self._nick))
                self._logintoken = hitbox_get_user_token \
                    .obtain_token(self._nick, self._pass)
                self.authenticate()
            elif self._nick == None:
                self._log.debug("USER before NICK, ignoring")
                return
            elif self._pass == None:
                self._log.debug("USER before PASS, sending error")
                text = "464 {} :No password given.  Closing connection" \
                    .format(self._nick)
                asyncio.ensure_future(self.send(text))
                asyncio.ensure_future(self.disconnect())
        else:
            self._log.debug(
                "User {} attempted reregistration".format(self._nick))
            asyncio.ensure_future(
                self.send("462 {} :You have already registered." \
                .format(self._nick)))

    @asyncio.coroutine
    def on_join(self, tok):
        """Called by data_received in response to a JOIN command.  This command
        handles the creation of a new Hitbox WS object, and sends it off to the
        handle_socket function to handle incoming messages.
            :tok: An array of tokens parsed from the command
        """
        if not self._loggedin:
            self._log.debug("JOIN before registration, ignoring")
        else:
            channel = tok[0].lstrip("#").lower()
            self._log.debug("Joining {}".format(channel))
            self._channels[channel] = HitboxClient(channel, self._nick,
            self._logintoken)
            asyncio.ensure_future(self._channels[channel].connect())
            yield from self.handle_socket(channel)

    @asyncio.coroutine
    def on_part(self, tok):
        """Called by data_received in response to a PART command.  This command
        handles the deletion of a specific Hitbox WS object.
            :tok: An array of tokens parsed from the command
        """
        if self._loggedin:
            c = tok[0].lstrip("#").lower()
            self._log.debug(tok[0])
            self._log.debug(tok[0].lstrip("#").lower())
            yield from self._channels[c].close_connection()
            self._channels[c] = None
            self._log.debug("Connection to #{} closed." \
                .format(c))

    @asyncio.coroutine
    def on_quit(self, tok):
        """Called by data_received in response to a QUIT command.  This command
        handles the deletion of all associated Hitbox WS objects.
            :tok: An array of tokens parsed from the command
        """
        if self._loggedin:
            for k, c in self._channels.items():
                try:
                    yield from c.close_connection()
                    self._channels[k] = None
                    self._log.debug("Connection to #{} closed." \
                        .format(k))
                except AttributeError:
                    self._log.debug("All connections closed due to disconnect.")

    @asyncio.coroutine
    def on_privmsg(self, tok):
        """Called by data_received in response to a PRIVMSG command.  This
        command handles sending messages to either another user or a chhannel.
            :tok: An array of tokens parsed from the command
        """
        if self._loggedin:
            if tok[0][0] == "#":
                c = tok[0].lstrip("#").lower()
                t = "".join(tok[1:])[1:]
                yield from self._channels[c].sendMessage(t)

    @asyncio.coroutine
    def handle_socket(self, channel):
        """This command handles incoming messages from the Hitbox WS object.
        When the user parts the channel, the client object is set to None,
        so the while loop can break out.  Individual messages are handed off to
        a handle_*** command.
            :channel: Channel name to handle incoming messages for
        """
        self._log.debug("Socket handler for {} established." \
            .format(channel))
        while self._channels[channel] != None:
            msg = yield from self._channels[channel].getNextMessage()
            self._log.debug("incoming message from {}: {}" \
                .format(channel, msg))
            j = json.loads(msg)
            #yes, this code is correct
            cmd = json.loads(j["args"][0])["method"]
            func = getattr(self, "handle_{}".format(cmd), None)
            if func != None:
                self._log.debug("Calling on_{}".format(cmd))
                asyncio.ensure_future(func(json.loads(j["args"][0])))
            else:
                self._log.warning("Unknown HB command {}({})".format(cmd, j))

    @asyncio.coroutine
    def handle_loginMsg(self, json):
        """This command handles incoming join messages.  This is sent by the
        server in response to a JOIN command issued by the client.
            :json: Parsed JSON.
        """
        yield from self.sendn("JOIN :#{}".format(json["params"]["channel"]))

    @asyncio.coroutine
    def handle_chatMsg(self, json):
        """This command handles incoming chat messages.  This is sent by the
        server either because of buffered text on a JOIN, or because someone
        actually sent a message.  If it was due to the first,
        json["params"]["buffer"] will be set to true.
            :json: Parsed JSON.
        """
        if json["params"]["name"] != self._nick:
            yield from self.sendn("PRIVMSG #{} :{}" \
                .format(json["params"]["channel"], json["params"]["text"]),
                nick=json["params"]["name"])

    def authenticate(self):
        """Check the authentication result.  If OK, send the welcome message.
        If it fails, disconnect the user."""
        if self._logintoken == None:
            text = ("464 {} :Invalid password given.  Closing connection") \
                .format(self._nick)
            asyncio.ensure_future(self.send(text))
            asyncio.ensure_future(self.disconnect())
        else:
            self._loggedin = True
            asyncio.ensure_future(self.welcome())

    @asyncio.coroutine
    def welcome(self):
        """Called after a successful registration to alert the clent that they
        have been logged in."""
        yield from self.send(
            ("001 {} :Welcome to the IRC Relay Network {}! {}@hitbox_irc_proxy")
            .format(self._nick, self._nick, self._nick))
        yield from self.send(
            ("002 {} :Your host is hitbox_irc_proxy, running v2.0")
            .format(self._nick))
        yield from self.send(
            ("003 {} :This server was created 5/6 3:40 PM")
            .format(self._nick))
        yield from self.send(
            ("005 {} PREFIX=(qaohv)~&@%+ CHANMODES=fm " +
            ":are supported by this server")
            .format(self._nick))

    @asyncio.coroutine
    def send(self, data):
        """Sends the data to the client after prepending the server ID."""
        b = (":hitbox_irc_proxy " + data + "\n").encode("UTF-8")
        self._log.info(">> {}".format(b.decode("UTF-8").strip()))
        self._transport.write(b)

    @asyncio.coroutine
    def sendn(self, data, nick=None):
        """Sends the data to the client after prepending the nick info."""
        if nick == None:
            nick = self._nick
        b = (":{}!{}@hitbox_irc_proxy " \
            .format(nick, nick) + data + "\n").encode("UTF-8")
        self._log.info(">> {}".format(b.decode("UTF-8").strip()))
        self._transport.write(b)

    @asyncio.coroutine
    def disconnect(self):
        """Disconnects the client gracefully."""
        self._transport.close()

if __name__ == "__main__":
    logs = [logging.getLogger(x) for x in ["irc", "asyncio", "main", "token",
    "ws"]]
    ch = logging.StreamHandler()
    ch.setLevel(config.logLevel)
    formatter = logging.Formatter(config.logFormat)
    ch.setFormatter(formatter)
    for x in logs:
        x.setLevel(config.logLevel)
        x.addHandler(ch)

    loop = asyncio.get_event_loop()
    coro = loop.create_server(IRCServerProtocol, port=7778)
    server = loop.run_until_complete(coro)
    thislog = logging.getLogger("main")
    thislog.info("Serving requests on {}" \
        .format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt as e:
        thislog.info("Interrupted, closing connections...")
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()
