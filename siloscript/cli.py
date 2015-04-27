# Copyright (c) The SimpleFIN Team
# See LICENSE for details.
import argparse
import sys
import os
import getpass
import gnupg
import json

from twisted.python.filepath import FilePath
from twisted.internet import endpoints, task, defer
from twisted.web.server import Site
from twisted.python import log
from twisted.python.procutils import which

from siloscript.server import PublicWebApp, ControlWebApp, DataWebApp
from siloscript.server import Machine
from siloscript.storage import MemoryStore, SQLiteStore, gnupgWrapper
from siloscript.process import SiloWrapper, LocalScriptRunner

root = FilePath(__file__).parent()


def getStore(args):
    """
    Get the right data store for the given command line args.
    """
    store = None
    if args.sqlite:
        # sqlite
        store = SQLiteStore.create(args.sqlite)
        log.msg('sqlite: %r' % (args.sqlite,), system='storage')
    else:
        # in-memory
        store = MemoryStore()
        log.msg('memory', system='storage')

    # layer on the encryption
    gpg = gnupg.GPG(
        homedir=args.gpg_home,
        binary=which('gpg')[0])
    return gnupgWrapper(gpg, store, passphrase=args.gpg_passphrase)



parser = argparse.ArgumentParser()

parser.add_argument('--sqlite',
    default=None,
    help='If given, then use SQLite as the storage mechanism.  This arg is '
         'the filename to store things in.')
parser.add_argument('--gpg-home', '-G',
    default='.gpghome',
    help='The directory where gpg keys live')
parser.add_argument('--prompt-passphrase', '-P',
    action='store_true',
    help='Prompt for the passphrase before running.')
parser.set_defaults(gpg_passphrase=None)


subparsers = parser.add_subparsers(help='sub-command help')


def serve(reactor, args):
    """
    Start webserver
    """
    log.startLogging(sys.stdout)
    store = getStore(args)
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

    return defer.Deferred()


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



@defer.inlineCallbacks
def run(reactor, args):
    """
    Run a single command
    """
    if args.verbose:
        log.startLogging(sys.stderr)
    script_root = FilePath(args.script).parent()

    store = getStore(args)
    runner = SiloWrapper('unknown', LocalScriptRunner(script_root.path))
    machine = Machine(store, runner)

    # start the server
    data_app = DataWebApp(machine)
    ep = endpoints.serverFromString(reactor, 'tcp:0:interface=127.0.0.1')
    p = yield ep.listen(Site(data_app.app.resource()))
    host = p.getHost()
    runner.data_url_root = 'http://%s:%s' % (host.host, host.port)
    
    # open a channel
    chan = machine.channel_open()
    def receiver(question):
        answer = getpass.getpass(question['prompt'] + ' ')
        machine.answer_question(question['id'], answer)
    machine.channel_connect(chan, receiver)

    # prepare output
    out_fd = sys.__stdout__
    if args.output != '-':
        out_fd = open(args.output, 'wb')

    def logger(msg):
        if msg['type'] == 'output':
            if msg['channel'] == 1:
                out_fd.write(msg['data'])
            else:
                sys.stderr.write(msg['data'])
        
        if args.verbose:
            sys.stderr.write(json.dumps(msg) + '\n')

    # run the script
    script_name = FilePath(args.script).basename()
    out, err, rc = yield machine.run(args.user, script_name,
        args.args, os.environ.copy(), chan, logger=logger)
    
    sys.exit(rc)



run_parser = subparsers.add_parser('run', help='Run a single siloscript'
    ' and get input from the commandline')
run_parser.add_argument('--output', '-o',
    type=str,
    default='-',
    help="Filename to write output to.  Defaults to stdout.")
run_parser.add_argument('--user', '-u',
    type=str,
    default='defaultuser',
    help="The user whose data should be used.")
run_parser.add_argument('--verbose', '-v',
    action='store_true',
    help="Verbose output?")
run_parser.add_argument('script',
    help='Script to run')
run_parser.add_argument('args',
    metavar='ARG',
    nargs=argparse.REMAINDER,
    help='Extra args to pass to script')
run_parser.set_defaults(func=run)



def run():
    args = parser.parse_args()
    if args.prompt_passphrase:
        args.gpg_passphrase = getpass.getpass(
            'GPG passphrase (typing will be hidden): ')
    task.react(args.func, [args])
