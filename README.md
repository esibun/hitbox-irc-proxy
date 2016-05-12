# hitbox-irc-proxy
IRC proxy for Hitbox.tv

## Info
This is the rewrite for hitbox-irc-proxy.  Currently, only the basics are up and running, however implementing the rest of the commands should be relatively easy thanks to the way the code is written now.  Most of the API commands are currently unimplemented, however the basics work (joining, sending messages).

## Requirements
Python must be ≥ 3.4 (3.3 may also work if you install asyncio)
Required python modules:
- aiohttp
- requests
- websockets

If you are missing any of them, you may install them with either `easy_install` or `pip install`.  *Please be careful* - some distributions come with both Python 2 and Python 3 - if this is the case, you must make sure you are installing the modules to the correct Python version.  For example, on Ubuntu you must put a 3 after any commands to target your Python 3 installation.

## Configuration
Hitbox-irc-proxy supports basic configuration by modifying the parameters in the `config.py` file.  You may change the log format, or change the logging level.  In the future, there will be more options here.

## Usage
Run this command in a console:
````
python hitbox_irc_server.py
````

You may need to substitute `python` with `python3` on some Linux distributions such as Ubuntu.

Connect to your local machine with your favorite IRC client on port 7778 - nick must be your Hitbox username, and server password must be your Hitbox password, for example:

```/connect 127.0.0.1 7778```

## Contributing

Feel free to help contribute to the project by submitting a pull request.  Please note that if you plan on contributing, your commits must follow the following coding standard.  I don't have strict rules, but there are a few in place to make the code more readable and maintainable:

- All methods must be documented with pydoc
- Indents are with 4 spaces
- Lines must not exceed 80 characters in width.  If you exceed this, consider creating a new method, using a variable, or splitting the line in a place that makes sense.
- New methods should be appropriately spaced - group expressions together that go together
- Your commit must not create errors
