# hitbox-irc-proxy
IRC proxy for Hitbox.tv

Right now, the project is still pretty bare bones and in alpha state.

Python must be ≥ 3.0
Required python modules:
- ws4py
- requests

Usage:
````
python hitbox-irc.py
````

Connect to your local machine with your favorite IRC client - nick must be your Hitbox username, and server password must be your Hitbox password.

Right now, only joins, nicklist, and messages work, but more is coming very soon(tm).  Script tested working with HexChat and Weechat.
