# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.internet import defer, utils
from twisted.python.filepath import FilePath



class SiloWrapper(object):
    """
    I wrap runners so that they have a DATASTORE_URL environment variable
    when they run.
    """

    DATASTORE_URL_ENV_NAME = 'DATASTORE_URL'


    def __init__(self, data_url_root, runner):
        """
        XXX
        """
        self.data_url_root = data_url_root
        self.runner = runner


    def runWithSilo(self, silo_key, executable, args, env):
        """
        XXX
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
        XXX
        """
        self.root = FilePath(root)


    @defer.inlineCallbacks
    def run(self, executable, args, env):
        """
        Run a script.
        """
        script_fp = self.root
        for segment in executable.split('/'):
            script_fp = script_fp.child(segment)
        out, err, exit = yield utils.getProcessOutputAndValue(script_fp.path,
            args, env=env)
        defer.returnValue((out, err, exit))
