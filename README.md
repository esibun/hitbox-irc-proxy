# hitbox-irc-proxy
IRC proxy for Hitbox.tv

## Info
This is the rewrite branch for hitbox-irc-proxy.  Currently, the code isn't ready, however you can check out progress by running `python hitbox_irc_socket.py`.  This will connect to my Hitbox channel as an anonymous user.  Most of the API commands are currently unimplemented, and the IRC layer is completely unimplemented.

## Requirements
Python must be ≥ 3.4
Required python modules:
- aiohttp
- websockets

Additional required python modules for running tests:
- aio.testing
- asynctest

If you are missing any of them, you may install them with either `easy_install` or `pip install`.  *Please be careful* - some distributions come with both Python 2 and Python 3 - if this is the case, you must make sure you are installing the modules to the correct Python version.  For example, on Ubuntu you must put a 3 after any commands to target your Python 3 installation.

## Usage

Run this command in a console:
````
python hitbox_irc.py
````

You may need to substitute `python` with `python3` on some Linux distributions such as Ubuntu.

Connect to your local machine with your favorite IRC client on port 7778 - nick must be your Hitbox username, and server password must be your Hitbox password, for example:

```/connect 127.0.0.1 7778```

## Contributing

Feel free to help contribute to the project by submitting a pull request.  Please note that if you plan on contributing, your commits must follow the following coding standard.  I don't have strict rules, but there are a few in place to make the code more readable and maintainable:

- All methods must be documented with pydoc
- Indents are with 4 spaces
- Lines must not exceed 80 characters in width
- Your commit must not create errors and must also pass all tests
