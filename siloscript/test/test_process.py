# Copyright (c) The SimpleFIN Team
# See LICENSE for details.

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.internet import defer

from siloscript.process import LocalScriptRunner, SiloWrapper
from siloscript.error import NotFound



class SiloWrapperTest(TestCase):

    
    @defer.inlineCallbacks
    def test_runWithSilo_DATASTORE_URL(self):
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
            env={'FOO': 'hey'},
            logger=None)
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


    @defer.inlineCallbacks
    def test_exists_and_within_path(self):
        root = FilePath(self.mktemp())
        root.makedirs()
        runner = LocalScriptRunner(root.path)
        yield self.assertFailure(runner.run('foo.sh'), NotFound)
        yield self.assertFailure(runner.run('ls'), NotFound)
        yield self.assertFailure(runner.run('/bin/echo', args=['hi']),
            NotFound)


    @defer.inlineCallbacks
    def test_path(self):
        root = FilePath(self.mktemp())
        root.makedirs()
        foo = root.child('foo.sh')
        foo.setContent('#!/bin/bash\npwd')
        runner = LocalScriptRunner(root.path)
        out, err, rc = yield runner.run('foo.sh')
        self.assertEqual(out, root.path + '\n', "Should set the path to the "
            "directory of the script")


    @defer.inlineCallbacks
    def test_logger(self):
        """
        You can get stdout, stderr as you go.
        """
        root = FilePath(self.mktemp())
        root.makedirs()
        foo = root.child('foo.sh')
        foo.setContent('#!/bin/bash\necho hello\necho stderr? 1>&2\necho $1')
        called = []
        def log(x):
            called.append(x)
        runner = LocalScriptRunner(root.path)
        out, err, rc = yield runner.run('foo.sh', logger=log)
        self.assertIn({'type': 'output', 'channel': 1, 'data': 'hello\n\n'},
            called)
        self.assertIn({'type': 'output', 'channel': 2, 'data': 'stderr?\n'},
            called)
        self.assertEqual(err, 'stderr?\n')
        self.assertEqual(out, 'hello\n\n')
        self.assertIn({'type': 'exit', 'code': 0}, called)
