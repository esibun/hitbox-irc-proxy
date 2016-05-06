# vim: sts=4:sw=4:et:tw=80:nosta
import aio.testing, asyncio, asynctest, logging, sys, unittest, websockets
from asynctest import CoroutineMock
from hitbox_irc_socket import HitboxClient
from unittest import TestCase, TextTestRunner, skipIf

NO_CONNECTIONS = True

class TestHitboxClient(TestCase):

    """ Handles testing the Hitbox IRC Proxy."""

    _serversMock = CoroutineMock(return_value=[
        {'server_ip': 'ec2-54-157-44-89.ch.hitbox.tv'},
        {'server_ip': 'ec2-23-20-88-5.ch.hitbox.tv'},
        {'server_ip': 'ec2-54-197-108-182.ch.hitbox.tv'},
        {'server_ip': 'ec2-54-90-230-120.ch.hitbox.tv'}
    ])

    @property
    def serversMock(self):
        return self._serversMock

    def setUp(self):
        """Set up asyncio before running tests."""

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    @skipIf(NO_CONNECTIONS, "This test requires a connection to the Hitbox API.")
    @aio.testing.run_until_complete
    def test_get_servers(self):
        """Check that get_servers() returns a list of servers"""

        hc = HitboxClient(channel="esi")
        res = yield from hc.get_servers()
        self.assertTrue(len(res) > 0, msg="""
    res = """ + str(res))

    @aio.testing.run_until_complete
    def test_select_server(self):
        """Check that select_server() returns a server from a list"""

        expected_servers = [
            'ec2-54-157-44-89.ch.hitbox.tv',
            'ec2-23-20-88-5.ch.hitbox.tv',
            'ec2-54-197-108-182.ch.hitbox.tv',
            'ec2-54-90-230-120.ch.hitbox.tv'
        ]

        hc = HitboxClient(channel="esi")
        hc.get_servers = self.serversMock
        res = yield from hc.select_server()
        self.assertIn(res, expected_servers, msg="""
    res = """ + str(res))

    @skipIf(NO_CONNECTIONS, "This test requires a connection to a Hitbox" +
    "chat server.")
    @aio.testing.run_until_complete
    def test_get_token(self):
        """Check that get_token() returns a token from the given server"""

        hc = HitboxClient(channel="esi")
        hc.get_servers = self.serversMock
        yield from hc.select_server()
        res = yield from hc.get_token()
        self.assertTrue(len(res) > 0, msg="""
    res = """ + str(res))

    @skipIf(NO_CONNECTIONS, "This test requires a connection to a Hitbox" +
    "chat server.")
    @aio.testing.run_until_complete
    def test_establish_connection(self):
        """Check that connect() returns a socket to a Hitbox server"""

        hc = HitboxClient(channel="esi")
        hc.get_servers = self.serversMock
        res = yield from hc.establish_connection()
        self.assertIsInstance(res, websockets.client.WebSocketClientProtocol, msg="""
    res = """ + str(res))
        yield from hc.close_connection()

    @aio.testing.run_until_complete
    def test_login(self):
        """Check that joinChannel() calls the right JSON"""

if __name__ == '__main__':
    unittest.main(testRunner=TextTestRunner())
