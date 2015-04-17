# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.internet import defer


from siloscript.process import LocalScriptRunner, SiloWrapper



class SiloWrapperTest(TestCase):

    
    @defer.inlineCallbacks
    def test_runsWith_DATASTORE_URL(self):
        """
        The datastore url should be computed and given as an environment
        variable to the runner.
        """
        root = FilePath(self.mktemp())
        root.makedirs()
        foo = root.child('foo.sh')
        foo.setContent('#!/bin/bash\necho $DATASTORE_URL\necho $FOO')

        wrapped = SiloWrapper('http://www.example.com/foo',
            LocalScriptRunner(root.path))
        
        out, err, rc = yield wrapped.runWithSilo(
            silo_key='THE-KEY',
            executable='foo.sh',
            args=['arg1'],
            env={'FOO': 'hey'})
        self.assertEqual(out, 'http://www.example.com/foo/THE-KEY\nhey\n',
            "Should use the generated DATASTORE_URL")
        self.assertEqual(err, '')
        self.assertEqual(rc, 0)




class LocalScriptRunnerTest(TestCase):
    

    @defer.inlineCallbacks
    def test_run(self):
        """
        Should run the script.
        """
        root = FilePath(self.mktemp())
        root.makedirs()
        foo = root.child('foo.sh')
        foo.setContent('#!/bin/bash\necho hello\necho $FOO\necho $1')
        runner = LocalScriptRunner(root.path)
        out, err, rc = yield runner.run('foo.sh', args=['arg1'], env={'FOO': 'hey'})
        self.assertEqual(out, 'hello\nhey\narg1\n')
        self.assertEqual(err, '')
        self.assertEqual(rc, 0)


    def test_executable(self):
        self.fail('write me: scripts must be executable')


    def test_exists(self):
        self.fail('write me: scripts must exist')


    def test_path(self):
        self.fail('write me: the path the script is run from should be set')
