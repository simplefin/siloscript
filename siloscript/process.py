# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer, protocol, reactor
from twisted.python.filepath import FilePath

from siloscript.error import NotFound



class SiloWrapper(object):
    """
    I wrap runners so that they have a DATASTORE_URL environment variable
    when they run.
    """

    DATASTORE_URL_ENV_NAME = 'DATASTORE_URL'


    def __init__(self, data_url_root, runner):
        """
        @param data_url_root: Root URL onto which silo keys will be appended
            when given to the running processes.
        @param runner: An object with a C{run} method of the same signature
            as L{LocalScriptRunner.run}.
        """
        self.data_url_root = data_url_root
        self.runner = runner


    def runWithSilo(self, silo_key, executable, args, env, logger=None):
        """
        Run a script with access to the given silo.

        @param silo_key: string silo key.
        @param executable: Script within the grasp of the runner to run.
        @param args: Any extra args to pass on command line when spawning
            process.
        @param env: Any additional environment variables to set for the process.
        """
        env.update({
            self.DATASTORE_URL_ENV_NAME: '%s/%s' % (
                self.data_url_root, silo_key),
        })
        return self.runner.run(executable, args, env, logger=logger)



class _ProcessProtocol(protocol.ProcessProtocol):

    
    def __init__(self, logger=None):
        self._stdout = []
        self._stderr = []
        self._done = defer.Deferred()
        self._logger = logger
        if not logger:
            # make logging a no-op
            self.logOutput = lambda *a,**kw: None
            self._log = lambda *a,**kw: None


    def _log(self, msg):
        self._logger(msg)


    def logOutput(self, channel, data):
        self._log({
            'type': 'output',
            'channel': channel,
            'data': data,
        })


    def stdout(self):
        return ''.join(self._stdout)


    def stderr(self):
        return ''.join(self._stderr)


    def outReceived(self, data):
        self._stdout.append(data)
        self.logOutput(1, data)


    def errReceived(self, data):
        self._stderr.append(data)
        self.logOutput(2, data)


    def processEnded(self, status):
        rc = status.value.exitCode
        self._log({
            'type': 'exit',
            'code': rc,
        })
        self._done.callback(rc)



class LocalScriptRunner(object):
    """
    I run scripts on the local file-system.  I'm a very thin wrapper around
    the tools provided by Twisted.
    """

    def __init__(self, root):
        """
        @param root: Root path of executable scripts.
        """
        self.root = FilePath(root)


    @defer.inlineCallbacks
    def run(self, executable, args=None, env=None, logger=None):
        """
        Run a script.

        @param logger: A function that will be called with stdout/stderr
            as the process runs.  It should expect a dict of data.
        """
        args = args or []
        env = env or {}
        script_fp = self.root
        for segment in executable.split('/'):
            script_fp = script_fp.child(segment)
        if not script_fp.exists():
            raise NotFound('Executable not found: %r' % (executable,))

        proto = _ProcessProtocol(logger=logger)
        reactor.spawnProcess(proto, executable,
            [executable] + args,
            env=env,
            path=script_fp.parent().path)
        rc = yield proto._done
        defer.returnValue((proto.stdout(), proto.stderr(), rc))

