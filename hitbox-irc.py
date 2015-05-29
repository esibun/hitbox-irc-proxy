import json, random, requests, socket, time
from ws4py.client.threadedclient import WebSocketClient
from threading import Thread, Event

class LoginException(BaseException):
	pass

class IRCServer:
	def __init__(self):
		self._connection = None
		self._connected = False
		self._ownMessage = False
		self._inOwnChannel = False
		self._negotiated = False
		self._receivedLoginMsg = False
		self._rejectOwn = True
		self._sendNames = False
		self._sendWho = False
		self._updateNames = False
		self._hitboxChat = {}
		self._nameslist = {}
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
					self._hitboxChat[self._username] = HitboxSocket(self)
					self._SendServerMessageToClient('NOTICE :hitbox-irc-proxy :IRC connected, logging into Hitbox...')
					try:
						self._hitboxChat[self._username].authenticate(self._username, self._password)
					except LoginException:
						self._SendServerMessageToClient('464 %s :Password given is invalid' % self._username)
						self._connected = False
						break
					self._SendServerMessageToClient('NOTICE hitbox-irc-proxy :Login successful, connecting to chat...')
					self._hitboxChat[self._username].connect()
					self._hitboxChat[self._username].stopFlag = Event()
					thread = self.NamesUpdateTimerThread(self._hitboxChat[self._username], self._username)
					thread.start()
					self._SendServerMessageToClient('NOTICE hitbox-irc-proxy :Connection successful!')
					self._SendServerMessageToClient('001 %s :Welcome to the IRC Relay Network %s! %s@hitbox-irc-proxy' % (self._username, self._username, self._username))
					self._SendServerMessageToClient('002 %s :Your host is hitbox-irc-proxy, running version pre-alpha' % self._username)
					self._SendServerMessageToClient('003 %s :This server was created 5/21 11:42 PM' % self._username)
					self._SendServerMessageToClient('005 %s PREFIX=(qaohv)~&@%%+ CHANMODES=fm :are supported by this server' % self._username)
					self._negotiated = True
			elif line[0] == 'QUIT':
				self._connected = False
				self._negotiated = False
			elif self._negotiated == True:
				if line[0] == 'JOIN':
					if line[1][1:] == self._username:
						if not self._inOwnChannel:
							self._hitboxChat[self._username].join(line[1][1:])
							self._inOwnChannel = True
					else:
						try:
							self._hitboxChat[line[1][1:]].join(line[1][1:])
						except KeyError:
							self._hitboxChat[line[1][1:]] = HitboxSocket(self)
							self._SendServerMessageToClient('NOTICE :hitbox-irc-proxy :Creating new WS connection for %s' % line[1][1:])
							self._hitboxChat[line[1][1:]].setLoginInfo(self._username, self._hitboxChat[self._username].grabToken())
							self._hitboxChat[line[1][1:]].connect()
							self._hitboxChat[line[1][1:]].join(line[1][1:])
					self._SendMessageToClient('JOIN %s' % line[1])
					self._hitboxChat[line[1][1:]].names(line[1][1:])
				elif line[0] == 'NAMES':
					if self._receivedLoginMsg == False:
						self._sendNames = True
					else:
						self._hitboxChat[line[1][1:]].names(line[1][1:])
				elif line[0] == 'PART':
					if line[1][1:] == self._username:
						self._inOwnChannel = False
						self._SendMessageToClient('PART %s' % line[1])
					else:
						try:
							self._hitboxChat[line[1][1:]].part()
							self._hitboxChat[line[1][1:]].disconnect()
							self._SendServerMessageToClient('NOTICE :hitbox-irc-proxy :Destroying WS connection for %s' % line[1][1:])
							del self._hitboxChat[line[1][1:]]
						except KeyError:
							pass
				elif line[0] == 'PING':
					self._SendRawMessageToClient('PONG %s' % ''.join(line[1:]))
				elif line[0] == 'PONG':
					for _, chat in self._hitboxChat.items():
						chat.pong()
				elif line[0] == 'PRIVMSG':
					self._ownMessage = True
					self._hitboxChat[line[1][1:]].privmsg(line[1][1:], ' '.join(line[2:])[1:])
				elif line[0] == 'WHO':
					if self._receivedLoginMsg == False:
						self._sendWho = True
					else:
						self._hitboxChat[line[1][1:]].who(line[1][1:])
				elif line[0] == 'COLOR':
					print(line[1])
					if len(line[1]) != 7:
						self._SendServerMessageToClient('461 COLOR :COLOR must be in HTML Hex format (#FFFFFF)')
					else:
						for _, chat in self._hitboxChat.items():
							chat.changeColor(line[1][1:])

	def HitboxMessage(self, line):
		if not self._negotiated:
			return
		if line == '2::':
			self._SendRawMessageToClient('PING :hitbox-irc-client')
			return
		line = line[4:]
		try:
			j = json.loads(line)
		except:
			return #throw away blank lines
		try:
			if j['args'][0]['method'] == 'chatMsg' and (j['args'][0]['param']['channel'] != self._username or self._inOwnChannel):
				self._SendMessageToClient('PRIVMSG #%s :%s' % (j['args'][0]['param']['channel'], j['args'][0]['param']['text']))
		except TypeError:
			#for some reason, most messages contain serialized json in the args, so we need to unserialize first - why, hitbox?
			j2 = json.loads(j['args'][0])
			try: name = j2['params']['name']
			except: pass
			try: channel = j2['params']['channel']
			except: pass
			try: data = j2['params']['data']
			except: pass
			if j2['method'] == 'loginMsg':
				self._receivedLoginMsg = True
				if self._sendNames == True:
					self._hitboxChat[channel].names(channel)
			elif j2['method'] == 'chatMsg' and (channel != self._username or self._inOwnChannel):
				self._SendPrivmsgToClient(name, 'PRIVMSG #%s :%s' % (channel, j2['params']['text']))
			elif j2['method'] == 'userList':
				if self._updateNames == True and not self._sendNames:
					oldnames = self._nameslist[channel]
					self._nameslist[channel] = []
					for admin in data['admin']:
						if channel.lower() == admin.lower():
							self._nameslist[channel].append('~%s' % admin)
						elif admin in data['isStaff'] or admin in data['isCommunity']:
							self._nameslist[channel].append('&%s' % admin)
						else:
							self._nameslist[channel].append('@%s' % admin)
					for user in data['user']:
						self._nameslist[channel].append('%%%s' % user)
					for anon in data['anon']:
						if anon in data['isSubscriber']:
							self._nameslist[channel].append('+%s' % anon)
						else:
							self._nameslist[channel].append('x%s' % anon)
					self._updateNames = False
					for name in oldnames:
						if name not in self._nameslist[channel]:
							nick = name#''.join(name[1:])
							self._SendPrivmsgToClient(nick, 'PART #%s' % channel)
					for name in self._nameslist[channel]:
						if name not in oldnames:
							nick = name#''.join(name[1:])
							self._SendPrivmsgToClient(''.join(name[1:]), 'JOIN #%s' % channel)
							if name[0] == '~':
								self._SendPrivmsgToClient('hitbox-irc-proxy', 'MODE #%s +q %s' % (channel, nick))
							elif name[0] == '&':
								self._SendPrivmsgToClient('hitbox-irc-proxy', 'MODE #%s +a %s' % (channel, nick))
							elif name[0] == '@':
								self._SendPrivmsgToClient('hitbox-irc-proxy', 'MODE #%s +o %s' % (channel, nick))
							elif name[0] == '%':
								self._SendPrivmsgToClient('hitbox-irc-proxy', 'MODE #%s +h %s' % (channel, nick))
							elif name[0] == '+':
								self._SendPrivmsgToClient('hitbox-irc-proxy', 'MODE #%s +v %s' % (channel, nick))
					return
				if self._sendNames == True:
					nameslist = []
					for admin in data['admin']:
						if channel.lower() == admin.lower():
							nameslist.append('~%s' % admin)
						elif admin in data['isStaff'] or admin in data['isCommunity']:
							nameslist.append('&%s' % admin)
						else:
							nameslist.append('@%s' % admin)
					for user in data['user']:
						nameslist.append('%%%s' % user)
					for anon in data['anon']:
						if anon in data['isSubscriber']:
							nameslist.append('+%s' % anon)
						else:
							nameslist.append('x%s' % anon)
					self._nameslist[channel] = nameslist
					for s, item in enumerate(nameslist):
						if item[0] == 'x':
							nameslist[s] = ''.join(item[1:])
					self._SendServerMessageToClient('353 %s = %s :%s' % (self._username, ''.join(['#', channel]), ' '.join(nameslist)))
					self._SendServerMessageToClient('366 %s %s :End of /NAMES list.' % (self._username, ''.join(['#', channel])))
					self._sendNames = False
					return
				for admin in data['admin']:
					if channel.lower() == admin.lower():
						self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy hitbox-irc-proxy %s H~ :0 hitbox-irc-proxy' % (self._username, ''.join(['#', channel]), admin, self._username))
					elif admin in data['isStaff'] or admin in data['isCommunity']:
						self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy hitbox-irc-proxy %s H& :0 hitbox-irc-proxy' % (self._username, ''.join(['#', channel]), admin, self._username))
					else:
						self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy hitbox-irc-proxy %s H@ :0 hitbox-irc-proxy' % (self._username, ''.join(['#', channel]), admin, self._username))
				for user in data['user']:
					self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy hitbox-irc-proxy %s H%% :0 hitbox-irc-proxy' % (self._username, ''.join(['#', channel]), user, self._username))
				for anon in data['anon']:
					if anon in data['isSubscriber']:
						self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy hitbox-irc-proxy %s H+ :0 hitbox-irc-proxy' % (self._username, ''.join(['#', channel]), anon, self._username))
					else:
						self._SendServerMessageToClient('352 %s %s %s hitbox-irc-proxy hitbox-irc-proxy %s H :0 hitbox-irc-proxy' % (self._username, ''.join(['#', channel]), anon, self._username))						
				self._SendServerMessageToClient('315 %s %s :End of /WHO list.' % (self._username, ''.join(['#', channel])))

	def _SendServerMessageToClient(self, message):
		print(''.join(['> ', ':hitbox-irc-proxy ', message]))
		self._connection.sendall(''.join([':hitbox-irc-proxy ', message, '\r\n']).encode('UTF-8'))

	def _SendMessageToClient(self, message):
		hostmask = ''.join([self._username, '!', self._username, '@hitbox-irc-proxy'])
		print(''.join(['> ', ':', hostmask, ' ', message]))
		self._connection.sendall(''.join([':', hostmask, ' ', message, '\r\n']).encode('UTF-8'))

	def _SendRawMessageToClient(self, message):
		print(''.join(['> ', message]))
		self._connection.sendall(''.join([message, '\r\n']).encode('UTF-8'))

	def _SendPrivmsgToClient(self, nick, message):
		if self._ownMessage: #don't echo back messages
			self._ownMessage = False
			return
		hostmask = ''.join([nick, '!', nick, '@hitbox-irc-proxy'])
		print(''.join(['> ', ':', hostmask, ' ', message]))
		self._connection.sendall(''.join([':', hostmask, ' ', message, '\r\n']).encode('UTF-8'))

	class NamesUpdateTimerThread(Thread):
		def __init__(self, event, channel):
			Thread.__init__(self)
			self.stopped = event.stopFlag
			self._chatObject = event
			self._channel = channel

		def run(self):
			while not self.stopped.wait(5):
				try:
					self._chatObject.namesUpdate(self._channel)
				except AttributeError:
					self.stopped.set()

	def setWho(self):
		self._sendWho = True

	def setNames(self):
		self._sendNames = True

	def updateNames(self):
		self._updateNames = True

class HitboxSocket:
	class _HitboxWS(WebSocketClient):
		def SetIRCObject(self, irc):
			self._irc = irc

		def received_message(self, message):
			if str(message) == '1::':
				print('~ CONNECTED')
			elif str(message) == '2::':
				print('< PING')
				self._irc.HitboxMessage(str(message))
			else:
				print(''.join(['< ', str(message)[4:]]))
				self._irc.HitboxMessage(str(message))

	def __init__(self, irc):
		self._color = "FF0000"
		self._connected = False
		self._id = None
		self._irc = irc
		self._server = None
		self._socket = None
		self._token = None
		self._username = None
		self.stopFlag = None

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

	def _SendPong(self):
		print('> PONG')
		self._socket.send('2::')
	
	def authenticate(self, username, password):
		data = {'login': username, 'pass': password, 'app': 'desktop'}
		r = requests.post('http://api.hitbox.tv/auth/token', data=data)
		if r.status_code == 400:
			raise LoginException('Invalid login - username or password invalid')
		json = r.json()
		self._token = json['authToken']
		self._username = username

	def grabToken(self):
		return self._token

	def setLoginInfo(self, username, authToken):
		self._token = authToken
		self._username = username

	def changeColor(self, color):
		self._color = color
		
	def connect(self):
		if self._token == None:
			raise Exception('Not authenticated, cannot connect')
		self._server = self._GetRandomServer()
		self._id = self._GetConnectionId()
		self._connected = True
		self._socket = self._HitboxWS(''.join(['ws://', self._server, '/socket.io/1/websocket/', self._id]))
		self._socket.SetIRCObject(self._irc)
		self._socket.connect()

	def disconnect(self):
		self.stopFlag.set()
		self._socket.close()

	def join(self, channel):
		if not self._connected:
			raise IOError('Not connected to server')
		query = {
			'name': 'message',
			'args': [{
				'method': 'joinChannel',
				'params': {
					'channel': channel.lower(),
					'name': self._username,
					'token': self._token,
					'isAdmin': True
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)

	def names(self, channel):
		if not self._connected:
			raise IOError('Not connected to server')
		self._irc.setNames()
		query = {
			'name': 'message',
			'args': [{
				'method': 'getChannelUserList',
				'params': {
					'channel': channel.lower()
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)

	def namesUpdate(self, channel):
		if not self._connected:
			raise IOError('Not connected to server')
		self._irc.updateNames()
		query = {
			'name': 'message',
			'args': [{
				'method': 'getChannelUserList',
				'params': {
					'channel': channel.lower()
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)

	def part(self, channel):
		if not self._connected:
			raise IOError('Not connected to server')
		query = {
			'name': 'message',
			'args': [{
				'method': 'partChannel',
				'params': {
					'channel': channel.lower(),
					'name': self._username
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)

	def pong(self):
		self._SendPong()
		
	def privmsg(self, channel, message):
		if not self._connected:
			raise IOError('Not connected to server')
		query = {
			'name': 'message',
			'args': [{
				'method': 'chatMsg',
				'params': {
					'channel': channel.lower(),
					'name': self._username,
					'nameColor': self._color,
					'text': message
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)

	def who(self, channel):
		if not self._connected:
			raise IOError('Not connected to server')
		self._irc.setWho()
		query = {
			'name': 'message',
			'args': [{
				'method': 'getChannelUserList',
				'params': {
					'channel': channel.lower()
				}
			}]
		}
		j = json.dumps(query)
		self._SendMessage(j)


IRCServer()