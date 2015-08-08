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

Connect to your local machine with your favorite IRC client on port 7778 - nick must be your Hitbox username, and server password must be your Hitbox password, for example:

```/connect 127.0.0.1 7778```

Right now, only joins, nicklist, and messages work.  I'm currently busy working on other projects, however hopefully I will return to implement the rest of the stuff in the near future.  Script tested working with HexChat and Weechat.
