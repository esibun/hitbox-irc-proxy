import json, random, requests, socket, time
from ws4py.client.threadedclient import WebSocketClient

pendingMessages = ''

class LoginException(BaseException):
	pass

class IRCServer:
	def __init__(self):
		self._connection = None
		self._connected = False
		self._negotiated = False
		self._receivedLoginMsg = False
		self._queuedWho = False
		self._hitboxChat = None
		self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._socket.bind(('', 7778))
		self._socket.listen(1)
		self._username = None
		self._password = None
		self._HandleClients()

	def _HandleClients(self):
		while True:
			self._connection, client_address = self._socket.accept()
			try:
				client_address
				self._connected = True

				while self._connected:
					self._HandleOutgoing()

					if self._negotiated:
						self._HandleIncoming()

			finally:
				self._connection.close()

	def _HandleOutgoing(self):
		data = self._connection.recv(4096).decode('UTF-8').split('\r\n')[:-1]
		for line in data:
			if line.split(' ')[0] != 'PASS':
				print(''.join(['< ', line]))
			else:
				print(''.join(['< ', 'PASS ****']))
			line = line.split(' ')
			line[0] = line[0].upper()
			if line[0] == 'NICK':
				self._username = line[1]
			elif line[0] == 'PASS':
				self._password = line[1]
			elif line[0] == 'USER':
				if self._username == None:
					pass
				elif self._password == None:
					self._SendServerMessageToClient('464 %s :No password given' % self._username)
					self._connected = False
				else:
					self._hitboxChat = HitboxSocket()
					self._SendServerMessageToClient('NOTICE :hitbox-irc-proxy :IRC connected, logging into Hitbox...')
					try:
						self._hitboxChat.authenticate(self._username, self._password)
					except LoginException:
						self._SendServerMessageToClient('464 %s :Password given is invalid' % self._username)
						self._connected = False
						break
					self._SendServerMessageToClient('NOTICE hitbox-irc-proxy :Login successful, connecting to chat...')
					self._hitboxChat.connect()
					self._SendServerMessageToClient('NOTICE hitbox-irc-proxy :Connection successful!')
					self._negotiated = True
			elif line[0] == 'QUIT':
				self._connected = False
				self._negotiated = False
			elif self._negotiated == True:
				if line[0] == 'JOIN':
					self._hitboxChat.join(line[1][1:])
					self._SendMessageToClient('JOIN %s' % line[1])
				elif line[0] == 'PRIVMSG':
					self._hitboxChat.privmsg(line[1][1:], ' '.join(line[2:])[1:])
				elif line[0] == 'WHO':
					if self._receivedLoginMsg == False:
						self._queuedWho = True
					else:
						self._hitboxChat.who(line[1][1:])

	def _HandleIncoming(self):
		global pendingMessages
		if pendingMessages != '':
			pendingMessages = pendingMessages.split('\r\n')[:-1]
			for line in pendingMessages:
				line = line[4:]
				line = json.loads(line)
				print(line)

				if line['args']['method'] == 'chatMsg':
					self._SendMessageToClient('PRIVMSG #%s :%s' % (line['args']['param']['channel'], line['args']['param']['text']))
				elif line['args']['method'] == 'userList':
					for admin in line['args']['params']['data']['admin']:
						if line['args']['params']['channel'] == admin:
							self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy %s H~ :0 hitbox-irc-proxy' % (self._username, ''.join(['#', line['args']['param']['channel']]), admin, self._username))
						elif admin in line['args']['params']['data']['isStaff'] or admin in line['args']['params']['data']['isCommunity']:
							self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy %s H& :0 hitbox-irc-proxy' % (self._username, ''.join(['#', line['args']['param']['channel']]), admin, self._username))
						else:
							self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy %s H@ :0 hitbox-irc-proxy' % (self._username, ''.join(['#', line['args']['param']['channel']]), admin, self._username))
					for user in line['args']['params']['data']['user']:
						self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy %s H% :0 hitbox-irc-proxy' % (self._username, ''.join(['#', line['args']['param']['channel']]), user, self._username))
					for anon in line['args']['params']['data']['anon']:
						self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy %s H :0 hitbox-irc-proxy' % (self._username, ''.join(['#', line['args']['param']['channel']]), user, self._username))						
					self._SendServerMessageToClient('315 %s %s :End of /WHO list.' % (self._username, line['args']['param']['channel']))
				else:
					try:
						#for some reason, some messages contain serialized json in the args, so we need to unserialize first
						j = json.loads(line['args'])
						if j['method'] == 'loginMsg':
							self._receivedLoginMsg = True
							if self._queuedWho == True:
								self._hitboxChat.who(line[1][1:])
					except:
						pass
			pendingMessages = ''

	def _SendServerMessageToClient(self, message):
		print(''.join(['> ', ':hitbox-irc-proxy ', message]))
		self._connection.sendall(''.join([':hitbox-irc-proxy ', message, '\r\n']).encode('UTF-8'))

	def _SendMessageToClient(self, message):
		hostmask = ''.join([self._username, '!', self._username, '@hitbox-irc-proxy'])
		print(''.join(['> ', ':', hostmask, ' ', message]))
		self._connection.sendall(''.join([':', hostmask, ' ', message, '\r\n']).encode('UTF-8'))

class HitboxSocket:
	class _HitboxWS(WebSocketClient):
		def received_message(self, message):
			global pendingMessages
			if str(message) == '1::':
				print('~ CONNECTED')
			elif str(message) == '2::':
				print('< PING')
				self.send('2::')
				print('> PONG')
			else:
				pendingMessages = ''.join([pendingMessages, str(message)])
				print(''.join(['< ', str(message)[4:]]))

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

	def who(self, channel):
		if not self._connected:
			raise IOError('Not connected to server')
		query = {
			'name': 'message',
			'args': [{
				'method': 'getChannelUserList',
				'params': {
					'channel': channel
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)


IRCServer()