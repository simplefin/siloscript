# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.python.filepath import FilePath
from twisted.internet import reactor, endpoints
from twisted.web.server import Site
import argparse

root = FilePath(__file__).parent()



parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(help='sub-command help')


def serve(args):
    """
    Start webserver
    """
    import sys
    from twisted.python import log
    from siloscript.server import PublicWebApp, ControlWebApp, DataWebApp
    from siloscript.server import Machine
    from siloscript.storage import MemoryStore
    from siloscript.process import SiloWrapper, LocalScriptRunner

    log.startLogging(sys.stdout)
    store = MemoryStore()
    runner = SiloWrapper(args.data_url, LocalScriptRunner(args.scripts))
    machine = Machine(store, runner)

    public_app = PublicWebApp(machine)
    endpoints.serverFromString(reactor, args.public_endpoint)\
        .listen(Site(public_app.app.resource()))

    control_app = ControlWebApp(machine, args.static_root)
    endpoints.serverFromString(reactor, args.control_endpoint)\
        .listen(Site(control_app.app.resource()))

    data_app = DataWebApp(machine)
    endpoints.serverFromString(reactor, args.data_endpoint)\
        .listen(Site(data_app.app.resource()))

    reactor.run()


server_parser = subparsers.add_parser('serve', help='Start HTTP server')

server_parser.add_argument('--control-endpoint', '-c',
    type=str,
    default='tcp:7600',
    help='Endpoint to serve control HTTP server on. This should NOT be exposed'
         ' to the public Internet.  (default: %(default)s)')

server_parser.add_argument('--data-endpoint', '-d',
    type=str,
    default='tcp:8600',
    help='Endpoint to serve data HTTP server on. This should NOT be exposed'
         ' to the public Internet.  (default: %(default)s)')
server_parser.add_argument('--data-url',
    type=str,
    default='http://127.0.0.1:8600',
    help='Base URL for the data endpoint as reachable by scripts.'
         '  (default: %(default)s)')

server_parser.add_argument('--public-endpoint', '-p',
    type=str,
    default='tcp:9600',
    help='Endpoint to serve public HTTP server on. This SHOULD be exposed'
         ' to the public Internet.  (default: %(default)s)')

server_parser.add_argument('--scripts', '-s',
    default=root.child('data').child('scripts').path,
    help='Path to executable scripts.  (default: %(default)s)')

server_parser.add_argument('--static-root', '-S',
    default=root.child('data').child('static').path,
    help='Path to static files served at /static.  (default: %(default)s)')
server_parser.set_defaults(func=serve)


def run():
    args = parser.parse_args()
    args.func(args)
