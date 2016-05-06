import asyncio, aiohttp, json, sys

class config:
	API_URL = "https://api.hitbox.tv"

@asyncio.coroutine
def obtain_token(user, password):
	j = json.dumps({
		"login": user,
		"pass": password,
		"rememberme": ""
	})
	print(user)
	print(password)
	r = yield from aiohttp.request("POST", "{}/auth/login".format(config.API_URL), data=j)
	d = yield from r.read()
	j = json.loads(d.decode("UTF-8"))
	if "error_msg" in j and j["error_msg"] == "auth_failed":
		print("Error: Authentication failed.")
		return
	else:
		print("Success! Here's your auth token:")
		print(j["authToken"])

if len(sys.argv) < 2:
	print("Usage: python hitbox_get_user_token.py <nick> <pass>")
	print()
	print("nick - Hitbox username")
	print("pass - Hitbox password")
else:
	nick = sys.argv[1]
	password = sys.argv[2]
	loop = asyncio.get_event_loop()
	try:
		loop.run_until_complete(obtain_token(nick, password))
	finally:
		loop.close()

