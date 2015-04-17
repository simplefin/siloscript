# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.python.filepath import FilePath
import argparse

root = FilePath(__file__).parent()



parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(help='sub-command help')


def serve(args):
    import sys
    from twisted.python import log
    from siloscript.server import UIServer
    from siloscript.storage import MemoryStore

    log.startLogging(sys.stdout)
    store = MemoryStore()
    server = UIServer(store, args.scripts,
        static_root=args.static_root)
    server.app.run('0.0.0.0', args.port)


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
