import json, random, requests, time
from ws4py.client.threadedclient import WebSocketClient

class LoginException(BaseException):
	pass

class HitboxSocket:
	class _HitboxWS(WebSocketClient):
		def received_message(self, message):
			if str(message) == '1::':
				print('~ CONNECTED')
			elif str(message) == '2::':
				self.send('2::')
			else:
				print(''.join(['< ', str(message)[3:]]))

	def __init__(self):
		self._connected = False
		self._id = None
		self._server = None
		self._socket = None
		self._token = None
		self._username = None

	def _GetRandomServer(self):
		r = requests.get('http://api.hitbox.tv/chat/servers')
		json = r.json()
		return random.choice(json)['server_ip']
	
	def _GetConnectionId(self):
		r = requests.get(''.join(['http://', self._server, '/socket.io/1/']))
		return r.text.split(':')[0]

	def _SendMessage(self, message):
		print(''.join(['> ', message]))
		self._socket.send(''.join(['5:::', message]))
	
	def authenticate(self, username, password):
		data = {'login': username, 'pass': password, 'app': 'desktop'}
		r = requests.post('http://api.hitbox.tv/auth/token', data=data)
		if r.status_code == 400:
			raise LoginException('Invalid login - username or password invalid')
		json = r.json()
		self._token = json['authToken']
		self._username = username
		
	def connect(self):
		if self._token == None:
			raise Exception('Not authenticated, cannot connect')
		self._server = self._GetRandomServer()
		self._id = self._GetConnectionId()
		self._connected = True
		self._socket = self._HitboxWS(''.join(['ws://', self._server, '/socket.io/1/websocket/', self._id]))
		self._socket.connect()

	def join(self, channel):
		if not self._connected:
			raise IOError('Not connected to server')
		query = {
			'name': 'message',
			'args': [{
				'method': 'joinChannel',
				'params': {
					'channel': channel,
					'name': self._username,
					'token': self._token,
					'isAdmin': True
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)
		
	def privmsg(self, channel, message):
		if not self._connected:
			raise IOError('Not connected to server')
		query = {
			'name': 'message',
			'args': [{
				'method': 'chatMsg',
				'params': {
					'channel': channel,
					'name': self._username,
					'nameColor': 'FFFFFF',
					'text': message
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)

chat = HitboxSocket()
try:
	chat.authenticate('esi', 'password')
except LoginException as e:
	print(e)
	exit()
chat.connect()
chat.join('esi')
time.sleep(2)
chat.privmsg('esi', 'it works!')
chat._socket.run_forever()