# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer, utils
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


    def runWithSilo(self, silo_key, executable, args, env):
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
        return self.runner.run(executable, args, env)



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
    def run(self, executable, args=None, env=None):
        """
        Run a script.
        """
        args = args or []
        env = env or {}
        script_fp = self.root
        for segment in executable.split('/'):
            script_fp = script_fp.child(segment)
        if not script_fp.exists():
            raise NotFound('Executable not found: %r' % (executable,))
        out, err, exit = yield utils.getProcessOutputAndValue(script_fp.path,
            args, env=env, path=script_fp.parent().path)
        defer.returnValue((out, err, exit))
