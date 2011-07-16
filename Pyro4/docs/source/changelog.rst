Change Log
**********

**Pyro 4.8**

- Major additions to the documentation: tutorials, API docs, and much more.
- Polished many docstrings in the sources, they're used in the generation of the API docs.
- Unix domain socket support. Added :file:`unixdomainsock` example and unit tests.
- Added options to the name server and echo server to use unix domain sockets.
- Name server broadcast responder will attempt to guess the caller's correct network
  interface, and use that to respond with the name server location IP (instead of 0.0.0.0).
  This should fix some problems that occurred when the nameserver was listening on
  0.0.0.0 and the proxy couldn't connect to it after lookup. Added unit test.
- API change: async callbacks have been changed into the more general async "call chain",
  using the ``then()`` method. Added examples and unit tests.
- Async calls now copy the proxy internally so they don't serialize after another anymore.
- A python 2.6 compatibility issue was fixed in the unit tests.

**Pyro 4.7**

- AutoProxy feature! This is a very nice one that I've always wanted to realize in Pyro ever since
  the early days. Now it's here: Pyro will automatically take care of any Pyro
  objects that you pass around through remote method calls. It will replace them
  by a proxy automatically, so the receiving side can call methods on it and be
  sure to talk to the remote object instead of a local copy. No more need to
  create a proxy object manually.
  This feature can be switched off using the config item ``AUTOPROXY`` to get the old behavior.
  Added a new :file:`autoproxy` example and changed several old examples to make use of this feature.
- Asynchronous method calls: you can execute a remote method (or a batch of remote method) asynchronously,
  and retrieve the results sometime in the future. Pyro will take care of collecting
  the return values in the background. Added :file:`async` example.
- One-line-server-setup using ``Pyro4.Daemon.serveSimple``, handy for quickly starting a server with basic settings.
- ``nameserver.register()`` behavior change: it will now overwrite an existing registration with the same name unless
  you provide a ``safe=True`` argument. This means you don't need to ``unregister()``
  your server objects anymore all the time when restarting the server.
- added ``Pyro4.util.excepthook`` that you can use for ``sys.excepthook``
- Part of the new manual has been written, including a tutorial where two simple applications are built.

**Pyro 4.6**

- Added batch call feature to greatly speed up many calls on the same proxy. Pyro can do 180,000 calls/sec or more with this.
- Fixed handling of connection fail in handshake
- A couple of python3 fixes related to the hmac key
- More unit test coverage

**Pyro 4.5**

- Added builtin test echo server, with example and unittest. Try ``python -m Pyro4.test.echoserver -h``
- Made ``Pyro4.config`` into a proper class with error checking.
- Some Jython related fixes.
- Code cleanups (pep8 is happier now)
- Fixed error behaviour, no longer crashes server in some cases
- ``HMAC_KEY`` is no longer required, but you'll still get a warning if you don't set it

**Pyro 4.4**

- removed pickle stream version check (too much overhead for too little benefit).
- set no-inherit flag on server socket to prevent problems with child processes blocking the socket. More info: http://www.cherrypy.org/ticket/856
- added HMAC message digests to the protocol, with a user configurable secret shared key in ``HMAC_KEY`` (required).
  This means you could now safely expose your Pyro interface to the outside world, without risk
  of getting owned by malicious messages constructed by a hacker.
  You need to have enough trust in your shared key. note that the data is not encrypted,
  it is only signed, so you still should not send sensitive data in plain text.
