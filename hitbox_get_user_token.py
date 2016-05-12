# vim: sts=4:sw=4:et:tw=80:nosta
import config, logging, json, requests, sys

def obtain_token(user, password):
    """Attempts to grab a login token from Hitbox with the given username and
    password.
        :user: Username to login with
        :password: Password to login with
    
    """
    log = logging.getLogger("token")
    j = json.dumps({
        "login": user,
        "pass": password,
        "rememberme": ""
    })
    log.debug("Making request to /auth/login")
    r = requests.post("{}/auth/login".format(config.API_URL), data=j)
    j = r.json()

    if "error_msg" in j and j["error_msg"] == "auth_failed":
        log.error("Authentication failed.")
        return None
    else:
        log.info("Login successful!")
        log.info("Your authentication token is: " + j["authToken"])
        return j["authToken"]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hitbox_get_user_token.py <nick> <pass>")
        print()
        print("nick - Hitbox username")
        print("pass - Hitbox password")
    else:
        nick = sys.argv[1]
        password = sys.argv[2]

    logs = [logging.getLogger(x) for x in ["asyncio", "token"]]
    ch = logging.StreamHandler()
    ch.setLevel(config.logLevel)
    formatter = logging.Formatter(config.logFormat)
    ch.setFormatter(formatter)
    for x in logs:
        x.setLevel(config.logLevel)
        x.addHandler(ch)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(obtain_token(nick, password))
    finally:
        loop.close()

